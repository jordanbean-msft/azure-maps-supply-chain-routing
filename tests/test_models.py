from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from template_repository.models.location import Location
from template_repository.models.route_candidate import RouteCandidate
from template_repository.models.scenario import Scenario


def make_location(id: str = "supplier", kind: str = "supplier") -> Location:
    return Location.model_validate(
        {
            "id": id,
            "name": id,
            "kind": kind,
            "latitude": 47.6,
            "longitude": -122.3,
            "quantity": 10,
        }
    )


def test_scenario_round_trip_preserves_snake_case_and_defaults() -> None:
    scenario = Scenario(
        id="demo",
        name="Demo",
        departure_time=datetime(2026, 1, 1, tzinfo=UTC),
        locations=[make_location(), make_location("factory", "factory")],
    )
    serialized = scenario.model_dump_json()
    assert Scenario.model_validate_json(serialized) == scenario
    assert '"cost_profile"' in serialized
    assert '"departure_time"' in serialized


@pytest.mark.parametrize(
    "locations",
    [
        [make_location(), make_location()],
        [make_location(str(i)) for i in range(11)],
        [make_location(str(i), "factory") for i in range(4)],
    ],
)
def test_scenario_rejects_duplicate_or_excess_locations(locations: list[Location]) -> None:
    with pytest.raises(ValidationError):
        Scenario(id="demo", name="Demo", departure_time=datetime.now(UTC), locations=locations)


def test_scenario_requires_timezone_aware_departure() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        Scenario(id="demo", name="Demo", departure_time=datetime(2026, 1, 1))


@pytest.mark.parametrize(
    "geometry", [[[-181, 47], [-122, 48]], [[-122, 91], [-122, 48]], [[47, -122], [48, -122]]]
)
def test_route_rejects_out_of_range_lon_lat_geometry(geometry: list[list[float]]) -> None:
    with pytest.raises(ValidationError):
        RouteCandidate(
            id="route",
            supplier_id="supplier",
            factory_id="factory",
            geometry=geometry,
            distance_km=10,
            duration_minutes=15,
            source="simulated",
        )


@pytest.mark.parametrize("latitude", [float("nan"), float("inf"), 91])
def test_location_rejects_invalid_coordinates(latitude: float) -> None:
    with pytest.raises(ValidationError):
        Location(
            id="supplier",
            name="Supplier",
            kind="supplier",
            latitude=latitude,
            longitude=0,
            quantity=1,
        )
