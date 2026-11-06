import { Badge, Button } from "@fluentui/react-components";
import type {
    CostBreakdown,
    CostProfile,
    OptimizationRun,
    RouteCandidate,
    Scenario,
} from "./types";

function estimateCost(
    route: RouteCandidate,
    profile: CostProfile,
): CostBreakdown {
    const fuel = (route.distance_km * profile.fuel_liters_per_100_km) / 100;
    const parts = {
        distance_cost: route.distance_km * profile.distance_cost_per_km,
        driver_time_cost:
            ((route.duration_minutes +
                route.weather_delay_minutes +
                route.simulated_delay_minutes) /
                60) *
            profile.driver_cost_per_hour,
        toll_cost: route.toll_estimate,
        fuel_cost: fuel * profile.fuel_price_per_liter,
        carbon_cost:
            fuel * profile.emissions_kg_per_liter * profile.carbon_cost_per_kg,
        traffic_delay_penalty:
            (route.traffic_delay_minutes / 60) * profile.delay_penalty_per_hour,
        weather_delay_penalty:
            (route.weather_delay_minutes / 60) * profile.delay_penalty_per_hour,
        simulated_disruption_penalty:
            (route.simulated_delay_minutes / 60) *
            profile.delay_penalty_per_hour,
    };
    return {
        ...parts,
        total: Object.values(parts).reduce((sum, value) => sum + value, 0),
    };
}

const number = (value: number) =>
    value.toLocaleString(undefined, { maximumFractionDigits: 2 });
const money = (value: number, currency: string) => {
    try {
        return new Intl.NumberFormat(undefined, {
            style: "currency",
            currency,
        }).format(value);
    } catch {
        return `${number(value)} ${currency}`;
    }
};

interface Props {
    scenario: Scenario;
    result: OptimizationRun | null;
    previous: OptimizationRun | null;
    selected: string | null;
    onSelect: (id: string) => void;
    stale: boolean;
}

export default function RouteResults({
    scenario,
    result,
    previous,
    selected,
    onSelect,
    stale,
}: Props) {
    const currency = scenario.cost_profile.currency;
    const fuelOverride = scenario.disruptions.find(
        (item) => item.enabled && item.kind === "fuel_price",
    );
    const effectiveProfile = {
        ...scenario.cost_profile,
        fuel_price_per_liter:
            fuelOverride?.fuel_price_per_liter ??
            scenario.cost_profile.fuel_price_per_liter,
    };
    const locations = new Map(
        scenario.locations.map((location) => [location.id, location]),
    );
    const selectedRoute = result?.routes.find((route) => route.id === selected);
    const allocations = new Map(
        result?.allocations
            .filter((allocation) => allocation.quantity > 0)
            .map((allocation) => [allocation.route_id, allocation]),
    );
    const selectedAllocation =
        selectedRoute && allocations.get(selectedRoute.id);
    const costs = selectedRoute
        ? (selectedAllocation?.unit_cost ??
          estimateCost(selectedRoute, effectiveProfile))
        : null;
    const quantity =
        selectedAllocation?.quantity ??
        (selectedRoute
            ? (locations.get(selectedRoute.supplier_id)?.quantity ?? 0)
            : 0);
    const sorted = [...(result?.routes ?? [])].sort((a, b) => {
        const cost = (route: RouteCandidate) =>
            allocations.get(route.id)?.unit_cost.total ??
            estimateCost(route, effectiveProfile).total;
        return (
            Number(allocations.has(b.id)) - Number(allocations.has(a.id)) ||
            cost(a) - cost(b) ||
            a.id.localeCompare(b.id)
        );
    });
    return (
        <section
            className="panel results-panel"
            aria-labelledby="results-title"
        >
            <div className="panel-heading">
                <div>
                    <h2 id="results-title">Shipment plan and route options</h2>
                </div>
                <Badge appearance="tint" color={stale ? "warning" : "subtle"}>
                    {stale
                        ? "Previous snapshot"
                        : result
                          ? "Completed snapshot"
                          : "No plan yet"}
                </Badge>
            </div>
            {!result ? (
                <div className="empty-state">
                    <h3>No routes yet</h3>
                    <p>
                        Save a scenario, then choose Calculate shipment plan.
                        The planner compares route costs and assigns supplier
                        quantities to factories within capacity.
                    </p>
                </div>
            ) : (
                <>
                    <div className="result-summary">
                        <div>
                            <span>Estimated plan cost</span>
                            <strong>
                                {money(result.total_cost, currency)}
                            </strong>
                        </div>
                        <div>
                            <span>Shipment units</span>
                            <strong>
                                {number(
                                    result.allocations.reduce(
                                        (sum, item) => sum + item.quantity,
                                        0,
                                    ),
                                )}
                            </strong>
                        </div>
                        <div>
                            <span>Recommended routes</span>
                            <strong>{allocations.size}</strong>
                        </div>
                        <div>
                            <span>Candidate routes</span>
                            <strong>{result.routes.length}</strong>
                        </div>
                        {previous && (
                            <div>
                                <span>
                                    Previous run total · saved assumptions
                                </span>
                                <strong>{number(previous.total_cost)}</strong>
                                <small>
                                    Compare only when currency and shipment
                                    scope match.
                                </small>
                            </div>
                        )}
                    </div>
                    <p className="plan-outcome">
                        The plan assigns{" "}
                        {number(
                            [...allocations.values()].reduce(
                                (sum, item) => sum + item.quantity,
                                0,
                            ),
                        )}{" "}
                        shipment units across {allocations.size} recommended{" "}
                        {allocations.size === 1 ? "route" : "routes"}.
                        Recommended routes are blue on the map. Selecting a
                        route only inspects it; it does not change this plan.
                    </p>
                    <p className="muted">
                        Recommended shipments first, then unused alternatives;
                        each group is ranked by unit cost. Alternatives carry no
                        shipments and show browser-estimated unit costs under
                        the editor assumptions. Only recommended rows contribute
                        to the plan cost. The cheapest individual route may not
                        be usable for every supplier because factory capacity is
                        limited. Tolls and weather risks are estimates.
                    </p>
                    <div className="table-scroll">
                        <table>
                            <caption className="sr-only">
                                Recommended shipments and unused route options.
                                Choose a route to inspect, not to change the
                                plan.
                            </caption>
                            <thead>
                                <tr>
                                    <th scope="col">Route / lane</th>
                                    <th scope="col">Source</th>
                                    <th scope="col">Distance</th>
                                    <th scope="col">ETA¹</th>
                                    <th scope="col">Traffic</th>
                                    <th scope="col">Weather risk²</th>
                                    <th scope="col">Toll²</th>
                                    <th scope="col">Quantity</th>
                                    <th scope="col">Unit cost</th>
                                    <th scope="col">Allocated total</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sorted.map((route, index) => {
                                    const allocation = allocations.get(
                                        route.id,
                                    );
                                    return (
                                        <tr
                                            key={route.id}
                                            data-route-id={route.id}
                                            className={[
                                                allocation && "recommended-row",
                                                selectedRoute?.id ===
                                                    route.id && "selected-row",
                                            ]
                                                .filter(Boolean)
                                                .join(" ")}
                                        >
                                            <th scope="row">
                                                <Button
                                                    type="button"
                                                    appearance="subtle"
                                                    className="route-button"
                                                    aria-pressed={
                                                        selectedRoute?.id ===
                                                        route.id
                                                    }
                                                    onClick={() =>
                                                        onSelect(route.id)
                                                    }
                                                >
                                                    <span className="route-rank">
                                                        {index + 1}
                                                    </span>{" "}
                                                    {locations.get(
                                                        route.supplier_id,
                                                    )?.name ??
                                                        route.supplier_id}{" "}
                                                    →{" "}
                                                    {locations.get(
                                                        route.factory_id,
                                                    )?.name ?? route.factory_id}
                                                    <small>
                                                        {allocation
                                                            ? `Recommended · ${number(allocation.quantity)} units`
                                                            : "Alternative · no shipments"}
                                                        {" · "}
                                                        Option{" "}
                                                        {result.routes
                                                            .filter(
                                                                (item) =>
                                                                    item.supplier_id ===
                                                                        route.supplier_id &&
                                                                    item.factory_id ===
                                                                        route.factory_id,
                                                            )
                                                            .findIndex(
                                                                (item) =>
                                                                    item.id ===
                                                                    route.id,
                                                            ) + 1}
                                                    </small>
                                                </Button>
                                            </th>
                                            <td>
                                                <span
                                                    className={`source ${route.source === "simulated" ? "simulated" : ""}`}
                                                >
                                                    {route.source ===
                                                    "simulated"
                                                        ? "Simulated"
                                                        : "Azure Maps"}
                                                </span>
                                            </td>
                                            <td>
                                                {number(route.distance_km)} km
                                            </td>
                                            <td>
                                                {number(
                                                    route.duration_minutes +
                                                        route.weather_delay_minutes +
                                                        route.simulated_delay_minutes,
                                                )}{" "}
                                                min
                                            </td>
                                            <td>
                                                {number(
                                                    route.traffic_delay_minutes,
                                                )}{" "}
                                                min
                                            </td>
                                            <td>
                                                {number(
                                                    route.weather_risk * 100,
                                                )}
                                                %
                                            </td>
                                            <td>
                                                {money(
                                                    route.toll_estimate,
                                                    currency,
                                                )}
                                            </td>
                                            <td>
                                                {number(
                                                    allocation?.quantity ?? 0,
                                                )}
                                            </td>
                                            <td>
                                                {money(
                                                    allocation?.unit_cost
                                                        .total ??
                                                        estimateCost(
                                                            route,
                                                            effectiveProfile,
                                                        ).total,
                                                    currency,
                                                )}
                                                {!allocation && " est."}
                                            </td>
                                            <td>
                                                {money(
                                                    allocation?.total_cost ?? 0,
                                                    currency,
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                    <p className="footnote">
                        ¹ ETA = drive time (already includes traffic) + weather
                        delay + simulated delay. ² Estimated, not guaranteed.
                        Cost per shipment unit scales linearly with quantity.
                    </p>
                    {!selectedRoute && (
                        <p className="muted">
                            Select a route on the map or in this table to
                            inspect its ETA and itemized costs.
                        </p>
                    )}
                    {selectedRoute && costs && (
                        <div className="cost-detail">
                            <div>
                                <h3>
                                    {locations.get(selectedRoute.supplier_id)
                                        ?.name ?? "Supplier"}
                                    {" → "}
                                    {locations.get(selectedRoute.factory_id)
                                        ?.name ?? "Factory"}
                                </h3>
                                <p>
                                    {selectedAllocation
                                        ? "Recommended shipment"
                                        : "Unused alternative · hypothetical estimate"}{" "}
                                    · {number(quantity)} units ×{" "}
                                    {money(costs.total, currency)} / unit
                                </p>
                                <strong className="cost-total">
                                    {money(
                                        selectedAllocation?.total_cost ??
                                            costs.total * quantity,
                                        currency,
                                    )}
                                </strong>
                                {!selectedAllocation && (
                                    <p className="muted">
                                        Hypothetical full supplier supply on
                                        this route. Capacity and other
                                        allocations are not re-solved by
                                        selecting a route.
                                    </p>
                                )}
                                <p className="muted">
                                    Weather delay:{" "}
                                    {number(
                                        selectedRoute.weather_delay_minutes,
                                    )}{" "}
                                    min · Simulated delay:{" "}
                                    {number(
                                        selectedRoute.simulated_delay_minutes,
                                    )}{" "}
                                    min
                                </p>
                            </div>
                            <dl className="cost-breakdown">
                                {Object.entries(costs)
                                    .filter(([key]) => key !== "total")
                                    .map(([key, value]) => (
                                        <div key={key}>
                                            <dt>{key.replaceAll("_", " ")}</dt>
                                            <dd>{money(value, currency)}</dd>
                                        </div>
                                    ))}
                                <div className="cost-sum">
                                    <dt>Total per unit</dt>
                                    <dd>{money(costs.total, currency)}</dd>
                                </div>
                            </dl>
                        </div>
                    )}
                    {result.warnings.length > 0 && (
                        <ul className="notice">
                            {result.warnings.map((warning, index) => (
                                <li key={index}>{warning}</li>
                            ))}
                        </ul>
                    )}
                </>
            )}
        </section>
    );
}
