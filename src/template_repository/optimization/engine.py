from decimal import Decimal

from ortools.graph.python import min_cost_flow

from template_repository.errors import ServiceError
from template_repository.models.allocation import Allocation
from template_repository.models.route_candidate import RouteCandidate
from template_repository.models.scenario import Scenario
from template_repository.optimization.costs import route_cost


def apply_disruptions(
    scenario: Scenario, routes: list[RouteCandidate]
) -> tuple[list[RouteCandidate], Scenario]:
    scenario = scenario.model_copy(deep=True)
    available = []
    for candidate in routes:
        route = candidate.model_copy(deep=True)
        closed = False
        for disruption in scenario.disruptions:
            if not disruption.enabled:
                continue
            touches = disruption.location_id in (route.supplier_id, route.factory_id)
            target = (
                disruption.route_id == route.id
                or touches
                or (not disruption.route_id and not disruption.location_id)
            )
            if disruption.kind == "road_closure" and target:
                closed = True
            elif disruption.kind == "facility_delay" and touches:
                route.simulated_delay_minutes += disruption.delay_minutes
            elif disruption.kind == "weather" and target:
                route.weather_risk = max(route.weather_risk, disruption.severity)
                route.weather_delay_minutes = max(
                    route.weather_delay_minutes, route.duration_minutes * disruption.severity * 0.3
                )
            elif disruption.kind == "fuel_price":
                scenario.cost_profile.fuel_price_per_liter = disruption.fuel_price_per_liter or 0
        if not closed:
            available.append(route)
    return available, scenario


def optimize(
    scenario: Scenario, routes: list[RouteCandidate]
) -> tuple[list[Allocation], list[RouteCandidate]]:
    suppliers = sorted((x for x in scenario.locations if x.kind == "supplier"), key=lambda x: x.id)
    factories = sorted((x for x in scenario.locations if x.kind == "factory"), key=lambda x: x.id)
    if not suppliers or not factories or sum(x.quantity for x in suppliers) <= 0:
        raise ServiceError(422, "Optimization requires suppliers, factories and positive supply.")
    routes, adjusted = apply_disruptions(scenario, routes)
    routes = sorted(
        routes, key=lambda route: (route_cost(route, adjusted.cost_profile).total, route.id)
    )
    solver = min_cost_flow.SimpleMinCostFlow()
    nodes = {location.id: index for index, location in enumerate(suppliers + factories)}
    sink = len(nodes)
    demand = sum(int(Decimal(str(x.quantity)) * 1000) for x in suppliers)
    max_cost = max(
        (round(route_cost(route, adjusted.cost_profile).total * 1000) for route in routes),
        default=0,
    )
    if demand * max_cost >= 2**60:
        raise ServiceError(
            422, "Quantity and cost combination exceeds the safe solver objective range."
        )
    costs = []
    for route in routes:
        cost = route_cost(route, adjusted.cost_profile)
        costs.append(cost)
        # Integer milliquantity and milli-currency coefficients. Input bounds keep
        # objective below int64; deterministic insertion order resolves equal costs.
        solver.add_arc_with_capacity_and_unit_cost(
            nodes[route.supplier_id], nodes[route.factory_id], demand, round(cost.total * 1000)
        )
    for supplier in suppliers:
        solver.set_node_supply(nodes[supplier.id], int(Decimal(str(supplier.quantity)) * 1000))
    for factory in factories:
        solver.add_arc_with_capacity_and_unit_cost(
            nodes[factory.id], sink, int(Decimal(str(factory.quantity)) * 1000), 0
        )
    solver.set_node_supply(sink, -demand)
    status = solver.solve()
    if status != solver.OPTIMAL:
        if status == solver.INFEASIBLE:
            return [], routes
        raise ServiceError(422, "Optimizer input exceeds the supported numerical range.")
    allocations = []
    for index, route in enumerate(routes):
        quantity = solver.flow(index) / 1000
        if quantity:
            allocations.append(
                Allocation(
                    route_id=route.id,
                    supplier_id=route.supplier_id,
                    factory_id=route.factory_id,
                    quantity=quantity,
                    unit_cost=costs[index],
                    total_cost=quantity * costs[index].total,
                )
            )
    return allocations, routes
