import json
import time
from unittest.mock import AsyncMock

import httpx
import pytest
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError

from template_repository.config import Settings
from template_repository.errors import ServiceError
from template_repository.persistence.memory import MemoryRepository
from template_repository.routing.azure_maps import AzureMapsRouting
from template_repository.seed import seed_scenario


def credential() -> AsyncMock:
    identity = AsyncMock()
    identity.get_token.return_value = AccessToken("private-token", int(time.time()) + 3600)
    return identity


def directions() -> dict:
    def collection(distance: int) -> dict:
        return {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiLineString",
                        "coordinates": [[[-122.3, 47.6], [-122.6, 45.5]]],
                    },
                    "properties": {
                        "type": "RoutePath",
                        "distanceInMeters": distance,
                        "durationInSeconds": 3600,
                        "durationTrafficInSeconds": 4200,
                        "legs": [],
                    },
                }
            ],
        }

    return dict(collection(100000), alternativeRoutes=[collection(120000)])


async def test_current_schema_matrix_directions_alternatives_weather_and_cache() -> None:
    requests = []
    scenario = seed_scenario()
    scenario.locations = [scenario.locations[0], scenario.locations[3]]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer private-token"
        assert request.headers["x-ms-client-id"] == "account"
        if request.url.path == "/route/matrix":
            return httpx.Response(
                200,
                json={
                    "type": "Feature",
                    "properties": {
                        "matrix": [
                            {
                                "originIndex": 0,
                                "destinationIndex": 0,
                                "statusCode": 200,
                                "distanceInMeters": 100000,
                                "durationTrafficInSeconds": 4200,
                            }
                        ]
                    },
                },
            )
        if request.url.path == "/route/directions":
            return httpx.Response(200, json=directions())
        return httpx.Response(
            200, json={"results": [{"hasPrecipitation": True, "wind": {"speed": {"value": 30}}}]}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        provider = AzureMapsRouting(
            http,
            credential(),
            Settings(_env_file=None, azure_maps_client_id="account"),
            MemoryRepository(),
        )
        routes, warnings = await provider.routes(scenario)
        assert len(routes) == 2 and routes[0].source == "azure_maps"
        assert routes[0].duration_minutes == 70 and routes[0].traffic_delay_minutes == 10
        assert routes[0].weather_risk == pytest.approx(0.6)
        assert routes[0].weather_delay_minutes > 0
        assert routes[0].toll_estimate == 0
        assert any("unpriced" in value for value in warnings)
        assert await provider.routes(scenario) == (routes, warnings)
        assert len(requests) == 3
    assert requests[0].url.params["api-version"] == "2025-01-01"
    assert requests[1].url.params["api-version"] == "2025-01-01"
    matrix_body = json.loads(requests[0].content)
    assert matrix_body["features"][0]["properties"]["pointType"] == "origins"
    assert matrix_body["travelMode"] == "truck" and matrix_body["traffic"] == "live"
    assert matrix_body["vehicleSpec"]["height"] == 4
    assert json.loads(requests[1].content)["maxRouteCount"] == 2


async def test_geocode_current_geojson_and_empty_results() -> None:
    payload = {
        "features": [
            {
                "properties": {"address": {"formattedAddress": "Seattle, WA"}},
                "geometry": {"type": "Point", "coordinates": [-122.3, 47.6]},
            }
        ]
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        result = await provider.geocode("Seattle")
        assert result[0].latitude == 47.6 and result[0].longitude == -122.3
        payload["features"] = []
        assert await provider.geocode("nowhere") == []


@pytest.mark.parametrize(
    "payload", [{}, {"features": [{}]}, {"features": [{"geometry": {"coordinates": []}}]}]
)
async def test_geocode_malformed_payload(payload: dict) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
    ) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        with pytest.raises(ServiceError, match="malformed"):
            await provider.geocode("Seattle")


@pytest.mark.parametrize("status", [401, 403, 429, 500])
async def test_http_failure_retry_budget_and_no_fallback(status: int) -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            status, json={"error": "private information"}, headers={"Retry-After": "0"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        with pytest.raises(ServiceError) as caught:
            await provider.geocode("Seattle")
    assert caught.value.status == 503 and "private" not in caught.value.detail
    assert len(requests) == (3 if status in {429, 500} else 1)


async def test_transient_throttle_then_success_and_identity_failure() -> None:
    count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal count
        count += 1
        return httpx.Response(
            429 if count == 1 else 200, json={"features": []}, headers={"Retry-After": "0"}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        identity = credential()
        provider = AzureMapsRouting(http, identity, Settings(_env_file=None), MemoryRepository())
        assert await provider.geocode("Seattle") == []
        assert count == 2
        identity.get_token.side_effect = ClientAuthenticationError("private secret")
        with pytest.raises(ServiceError, match="identity unavailable"):
            await provider.geocode("Seattle")


@pytest.mark.parametrize(
    "matrix",
    [
        {},
        {"properties": {"matrix": []}},
        {"properties": {"matrix": [{"originIndex": 99, "destinationIndex": 0, "statusCode": 200}]}},
    ],
)
async def test_missing_or_malformed_matrix_is_failure(matrix: dict) -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=matrix))
    ) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        with pytest.raises(ServiceError, match="malformed"):
            await provider.routes(seed_scenario())


async def test_no_route_cells_return_infeasible_candidates_not_fake_roads() -> None:
    scenario = seed_scenario()
    scenario.locations = [scenario.locations[0], scenario.locations[3]]
    matrix = {
        "properties": {"matrix": [{"originIndex": 0, "destinationIndex": 0, "statusCode": 404}]}
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=matrix))
    ) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        routes, _ = await provider.routes(scenario)
    assert routes == []


async def test_partial_weather_is_explicit_and_malformed_directions_fail() -> None:
    scenario = seed_scenario()
    supplier, factory = scenario.locations[0], scenario.locations[3]
    malformed = False

    def handler(request: httpx.Request) -> httpx.Response:
        if "weather" in request.url.path:
            return httpx.Response(200, json={"results": []})
        return httpx.Response(200, json={} if malformed else directions())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        routes, warnings = await provider._directions(scenario, supplier, factory)
        assert len(routes) == 2 and "not an observation" in warnings[0]
        malformed = True
        with pytest.raises(ServiceError, match="directions response"):
            await provider._directions(scenario, supplier, factory)


async def test_bad_json_and_network_failure() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content="not json"))
    ) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        with pytest.raises(ServiceError, match="JSON"):
            await provider.geocode("Seattle")

    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("network down", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        with pytest.raises(ServiceError, match="transport"):
            await provider.geocode("Seattle")
