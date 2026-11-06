import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from template_repository.config import Settings
from template_repository.persistence.memory import MemoryRepository
from template_repository.routing.azure_maps import AzureMapsRouting
from template_repository.routing.weather_sampling import forecast_samples
from template_repository.seed import seed_scenario
from tests.test_maps import credential, directions

NOW = datetime(2026, 11, 6, 20, 0, tzinfo=UTC)


def test_actual_road_vertices_and_departure_relative_offsets() -> None:
    geometry = [(-122.0, 47.0), (-123.0, 47.0), (-123.0, 46.0), (-122.0, 46.0)]
    samples, covered, warnings = forecast_samples(geometry, 80, NOW + timedelta(minutes=10), NOW)
    assert [(longitude, latitude) for latitude, longitude, _ in samples] == geometry
    assert [sample[2] for sample in samples] == sorted(sample[2] for sample in samples)
    assert samples[0][2] == 10 and samples[-1][2] == 90
    assert covered == 80 and warnings == []
    assert (-122.0, 46.5) not in [(longitude, latitude) for latitude, longitude, _ in samples]


def test_long_trip_horizon_and_sample_limit_do_not_claim_full_coverage() -> None:
    geometry = [(-122.0 + index / 100, 47.0) for index in range(101)]
    samples, covered, warnings = forecast_samples(geometry, 240, NOW, NOW)
    assert len(samples) == 12
    assert samples[0][2] == 0 and samples[-1][2] <= 120
    assert covered <= 120
    assert all((longitude, latitude) in geometry for latitude, longitude, _ in samples)
    assert "unpriced, not hazard-free" in warnings[0]
    samples, covered, warnings = forecast_samples(geometry, 60, NOW + timedelta(minutes=121), NOW)
    assert samples == [] and covered == 0 and "not an observation" in warnings[0]


async def test_weather_request_is_not_made_for_uncovered_future_departure() -> None:
    scenario = seed_scenario()
    scenario.departure_time = datetime.now(UTC) + timedelta(hours=4)
    provider = AzureMapsRouting(
        AsyncMock(), credential(), Settings(_env_file=None), MemoryRepository()
    )
    provider.request = AsyncMock(return_value=directions())
    routes, warnings = await provider._directions(
        scenario, scenario.locations[0], scenario.locations[3]
    )
    assert provider.request.await_count == 1
    assert all(route.weather_risk == 0 and route.weather_delay_minutes == 0 for route in routes)
    assert any("forecast horizon" in warning for warning in warnings)


@pytest.mark.parametrize(
    "waypoints",
    [
        [],
        [{"hazards": {"maxHazardIndex": 1}}],
        [{"hazards": {"maxHazardIndex": None}}] * 3,
        [{"hazards": {"maxHazardIndex": 5}}] * 3,
    ],
)
async def test_incomplete_or_invalid_forecast_never_claims_good_weather(waypoints: list) -> None:
    scenario = seed_scenario()
    scenario.departure_time = datetime.now(UTC) + timedelta(minutes=1)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/route/directions":
            return httpx.Response(200, json=directions())
        assert request.url.path == "/weather/route/json"
        return httpx.Response(
            200, json={"summary": {"hazards": {"maxHazardIndex": 1}}, "waypoints": waypoints}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        routes, warnings = await provider._directions(
            scenario, scenario.locations[0], scenario.locations[3]
        )
    assert all(route.weather_risk == 0 and route.weather_delay_minutes == 0 for route in routes)
    assert len([warning for warning in warnings if "not an observation" in warning]) == 2


async def test_past_departure_matrix_now_directions_default_and_forecast_offsets() -> None:
    scenario = seed_scenario()
    scenario.locations = [scenario.locations[0], scenario.locations[3]]
    scenario.departure_time = datetime.now(UTC) - timedelta(minutes=30)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/route/matrix":
            return httpx.Response(
                200,
                json={
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
                    }
                },
            )
        if request.url.path == "/route/directions":
            return httpx.Response(200, json=directions())
        assert request.url.path == "/weather/route/json"
        etas = [float(point.split(",")[2]) for point in request.url.params["query"].split(":")]
        assert etas[0] == 0 and etas[-1] == 70
        return httpx.Response(
            200,
            json={
                "summary": {"hazards": {"maxHazardIndex": 2}},
                "waypoints": [{"hazards": {"maxHazardIndex": 2}}] * 3,
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        provider = AzureMapsRouting(
            http, credential(), Settings(_env_file=None), MemoryRepository()
        )
        routes, warnings = await provider.routes(scenario)
    assert json.loads(requests[0].content)["departAt"] == "now"
    assert "departAt" not in json.loads(requests[1].content)
    assert any("past" in warning and "current departure" in warning for warning in warnings)
    assert routes[0].weather_delay_minutes == 70 * 0.5 * 0.3
