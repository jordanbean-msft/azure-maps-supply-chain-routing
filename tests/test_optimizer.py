import pytest
from pydantic import ValidationError

from template_repository.errors import ServiceError
from template_repository.models.cost_profile import CostProfile
from template_repository.models.disruption import Disruption
from template_repository.optimization.costs import route_cost
from template_repository.optimization.engine import apply_disruptions, optimize
from template_repository.routing.simulated import SimulatedRouting
from template_repository.seed import seed_scenario


async def test_solver_respects_supply_capacity_and_reproducibility() -> None:
    scenario = seed_scenario()
    routes, _ = await SimulatedRouting().routes(scenario)
    allocations, ranked = optimize(scenario, routes)
    assert allocations == optimize(scenario, list(reversed(routes)))[0]
    for supplier in [x for x in scenario.locations if x.kind == "supplier"]:
        assert (
            sum(x.quantity for x in allocations if x.supplier_id == supplier.id)
            == supplier.quantity
        )
    for factory in [x for x in scenario.locations if x.kind == "factory"]:
        assert (
            sum(x.quantity for x in allocations if x.factory_id == factory.id) <= factory.quantity
        )
    assert len(ranked) == 12
    assert [route_cost(x, scenario.cost_profile).total for x in ranked] == sorted(
        route_cost(x, scenario.cost_profile).total for x in routes
    )


async def test_excess_supply_or_prohibited_lanes_are_infeasible() -> None:
    scenario = seed_scenario()
    routes, _ = await SimulatedRouting().routes(scenario)
    for factory in scenario.locations:
        if factory.kind == "factory":
            factory.quantity = 0
    assert optimize(scenario, routes)[0] == []
    scenario = seed_scenario()
    scenario.disruptions = [
        Disruption(id=f"closure-{i}", name="Close", kind="road_closure", route_id=route.id)
        for i, route in enumerate(routes)
        if route.supplier_id == "seattle"
    ]
    assert optimize(scenario, routes)[0] == []


async def test_costs_eight_components_and_no_traffic_time_double_count() -> None:
    scenario = seed_scenario()
    routes, _ = await SimulatedRouting().routes(scenario)
    route = routes[0].model_copy(
        update={
            "duration_minutes": 60,
            "traffic_delay_minutes": 15,
            "weather_delay_minutes": 0,
            "simulated_delay_minutes": 0,
        }
    )
    profile = CostProfile(driver_cost_per_hour=30, delay_penalty_per_hour=60)
    cost = route_cost(route, profile)
    assert cost.driver_time_cost == 30
    assert cost.traffic_delay_penalty == 15
    assert cost.total == sum(value for key, value in cost.model_dump().items() if key != "total")
    scenario.disruptions = [
        Disruption(
            id="delay",
            name="Factory queue",
            kind="facility_delay",
            location_id=route.factory_id,
            delay_minutes=120,
        ),
        Disruption(id="weather", name="Storm", kind="weather", severity=1),
        Disruption(id="fuel", name="Fuel rise", kind="fuel_price", fuel_price_per_liter=10),
    ]
    adjusted_routes, adjusted_scenario = apply_disruptions(scenario, [route])
    changed = route_cost(adjusted_routes[0], adjusted_scenario.cost_profile)
    assert changed.fuel_cost > cost.fuel_cost
    assert changed.simulated_disruption_penalty > 0
    assert changed.weather_delay_penalty > 0
    assert scenario.cost_profile.fuel_price_per_liter == 1.5


async def test_milliquantity_precision_and_empty_input() -> None:
    scenario = seed_scenario()
    for location in scenario.locations:
        location.quantity = 0.001 if location.kind == "supplier" else 0.002
    routes, _ = await SimulatedRouting().routes(scenario)
    result, _ = optimize(scenario, routes)
    assert sum(x.quantity for x in result) == 0.003
    with pytest.raises(ValidationError, match="three decimal"):
        scenario.locations[0].model_validate(
            dict(scenario.locations[0].model_dump(), quantity=0.0001)
        )
    scenario.locations = []
    with pytest.raises(ServiceError, match="positive supply"):
        optimize(scenario, [])


async def test_extreme_but_bounded_inputs_cannot_overflow_solver() -> None:
    scenario = seed_scenario()
    for location in scenario.locations:
        location.quantity = 100000
    scenario.cost_profile = CostProfile(
        distance_cost_per_km=100,
        driver_cost_per_hour=1000,
        fuel_price_per_liter=100,
        fuel_liters_per_100_km=100,
        emissions_kg_per_liter=10,
        carbon_cost_per_kg=10,
        delay_penalty_per_hour=1000,
    )
    routes, _ = await SimulatedRouting().routes(scenario)
    routes = [
        route.model_copy(
            update={
                "distance_km": 10000,
                "duration_minutes": 20160,
                "weather_delay_minutes": 20160,
                "simulated_delay_minutes": 43200,
            }
        )
        for route in routes
    ]
    with pytest.raises(ServiceError, match="safe solver objective range"):
        optimize(scenario, routes)


@pytest.mark.parametrize(
    "profile",
    [{"currency": "ZZZ"}, {"fuel_price_per_liter": float("inf")}, {"driver_cost_per_hour": 1001}],
)
def test_invalid_or_unbounded_cost_assumptions(profile: dict) -> None:
    with pytest.raises(ValidationError):
        CostProfile(**profile)
