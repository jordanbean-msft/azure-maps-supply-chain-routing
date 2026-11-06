import json
import time
from datetime import UTC, datetime, timedelta
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
                        "coordinates": [
                            [
                                [-122.3, 47.6],
                                [-123.0 if distance == 100000 else -121.8, 47.1],
                                [-122.6, 45.5],
                            ]
                        ],
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


async def test_official_v2025_feature_collections_keep_main_and_alternative_paths_separate() -> (
    None
):
    # Reduced from the official v2025-01-01 Post Route Directions sample response:
    # learn.microsoft.com/rest/api/maps/route/post-route-directions?view=rest-maps-2025-01-01
    waypoint = {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [-122.20147, 47.60868]},
        "properties": {
            "type": "Waypoint",
            "order": {"inputIndex": 0},
            "routePathPoint": {"legIndex": 0, "pointIndex": 0},
        },
    }
    primary = {
        "type": "Feature",
        "geometry": {
            "type": "MultiLineString",
            "coordinates": [
                [[-122.20147, 47.60868], [-122.20346, 47.61016], [-122.2016, 47.61508]]
            ],
        },
        "properties": {
            "type": "RoutePath",
            "distanceInMeters": 1520,
            "durationInSeconds": 307,
            "durationTrafficInSeconds": 300,
            "legs": [
                {
                    "distanceInMeters": 1520,
                    "durationInSeconds": 307,
                    "durationTrafficInSeconds": 300,
                    "routePathRange": {"legIndex": 0, "range": [0, 64]},
                }
            ],
        },
    }
    alternative = {
        "type": "Feature",
        "geometry": {
            "type": "MultiLineString",
            "coordinates": [
                [[-122.20147, 47.60868], [-122.20149, 47.60997], [-122.2016, 47.61508]]
            ],
        },
        "properties": {
            "type": "RoutePath",
            "distanceInMeters": 713,
            "durationInSeconds": 92,
            "durationTrafficInSeconds": 90,
            "legs": [
                {
                    "distanceInMeters": 713,
                    "durationInSeconds": 92,
                    "durationTrafficInSeconds": 90,
                    "routePathRange": {"legIndex": 0, "range": [0, 29]},
                }
            ],
        },
    }
    response = {
        "type": "FeatureCollection",
        "features": [waypoint, primary],
        "alternativeRoutes": [{"type": "FeatureCollection", "features": [waypoint, alternative]}],
    }
    scenario = seed_scenario()
    scenario.departure_time = datetime.now(UTC) + timedelta(minutes=5)
    forecast_queries = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/route/directions":
            return httpx.Response(200, json=response)
        forecast_queries.append(request.url.params["query"])
        severity = len(forecast_queries)
        return httpx.Response(
            200,
            json={
                "summary": {"hazards": {"maxHazardIndex": severity}},
                "waypoints": [{"hazards": {"maxHazardIndex": severity}}] * 3,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        routes, _ = await provider._directions(
            scenario, scenario.locations[0], scenario.locations[3]
        )
    assert routes[0].distance_km == 1.52 and routes[0].duration_minutes == 5
    assert routes[1].distance_km == 0.713 and routes[1].duration_minutes == 1.5
    assert routes[0].geometry != routes[1].geometry
    assert routes[0].weather_risk == 0.25 and routes[1].weather_risk == 0.5
    assert "47.610160,-122.203460," in forecast_queries[0]
    assert "47.609970,-122.201490," in forecast_queries[1]


async def test_current_schema_matrix_directions_alternatives_weather_and_cache() -> None:
    requests = []
    scenario = seed_scenario()
    scenario.departure_time = datetime.now(UTC) + timedelta(minutes=5)
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
            200,
            json={
                "summary": {"hazards": {"maxHazardIndex": 3}},
                "waypoints": [{"hazards": {"maxHazardIndex": index}} for index in (0, 3, 1)],
            },
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
        assert routes[0].weather_risk == pytest.approx(0.75)
        assert routes[0].weather_delay_minutes > 0
        assert routes[0].toll_estimate == 0
        assert any("unpriced" in value for value in warnings)
        assert await provider.routes(scenario) == (routes, warnings)
        assert len(requests) == 4
    assert requests[0].url.params["api-version"] == "2025-01-01"
    assert requests[1].url.params["api-version"] == "2025-01-01"
    matrix_body = json.loads(requests[0].content)
    assert matrix_body["features"][0]["properties"]["pointType"] == "origins"
    assert matrix_body["travelMode"] == "truck" and matrix_body["traffic"] == "live"
    assert matrix_body["vehicleSpec"]["height"] == 4
    assert matrix_body["departAt"] == scenario.departure_time.isoformat()
    assert json.loads(requests[1].content)["maxRouteCount"] == 2
    assert json.loads(requests[1].content)["departAt"] == scenario.departure_time.isoformat()
    queries = [
        request.url.params["query"]
        for request in requests
        if request.url.path == "/weather/route/json"
    ]
    assert len(queries) == 2 and queries[0] != queries[1]
    assert "47.100000,-123.000000," in queries[0]
    assert "47.100000,-121.800000," in queries[1]
    for query in queries:
        etas = [float(point.split(",")[2]) for point in query.split(":")]
        assert 4.9 <= etas[0] <= 5 and 74.9 <= etas[-1] <= 75


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
