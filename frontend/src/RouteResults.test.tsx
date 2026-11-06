import { render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import RouteResults from "./RouteResults";
import { run, scenario } from "./test-fixtures";

it("explains the plan, distinguishes recommended shipments from alternatives and does not auto-inspect a route", () => {
    const view = render(
        <RouteResults
            scenario={scenario}
            result={run}
            previous={null}
            selected={null}
            onSelect={vi.fn()}
            stale={false}
        />,
    );
    expect(
        screen.getByText(
            /The plan assigns 50 shipment units across 1 recommended route/,
        ),
    ).toBeInTheDocument();
    expect(screen.getByText(/Recommended · 50 units/)).toBeInTheDocument();
    expect(screen.getByText(/Alternative · no shipments/)).toBeInTheDocument();
    expect(screen.queryByText("Recommended shipment")).not.toBeInTheDocument();
    expect(
        within(screen.getByRole("table")).getAllByRole("button", {
            pressed: false,
        }),
    ).toHaveLength(2);
    view.rerender(
        <RouteResults
            scenario={scenario}
            result={run}
            previous={null}
            selected="route-2"
            onSelect={vi.fn()}
            stale={false}
        />,
    );
    expect(
        screen.getByText(/Unused alternative · hypothetical estimate/),
    ).toBeInTheDocument();
    expect(
        screen.getByText(/The plan assigns 50 shipment units/),
    ).toBeInTheDocument();
});

it("estimates unallocated alternatives with effective zero-price fuel and complete driver time without changing allocation totals", () => {
    render(
        <RouteResults
            scenario={{
                ...scenario,
                disruptions: [
                    {
                        id: "fuel",
                        name: "Free fuel what-if",
                        kind: "fuel_price",
                        enabled: true,
                        route_id: null,
                        location_id: null,
                        delay_minutes: 0,
                        severity: 0,
                        fuel_price_per_liter: 0,
                    },
                ],
            }}
            result={run}
            previous={null}
            selected="route-2"
            onSelect={vi.fn()}
            stale={false}
        />,
    );
    const table = screen.getByRole("table");
    // Alternative: 470 distance + 110 driver + 8 toll + 31.49 carbon + 12.50 delay.
    expect(within(table).getByText("$631.99 est.")).toBeInTheDocument();
    expect(screen.getByText("$31,599.50")).toBeInTheDocument();
    expect(within(table).getByText("$10,000.00")).toBeInTheDocument();
    expect(
        screen.getByText(
            "Hypothetical full supplier supply on this route. Capacity and other allocations are not re-solved by selecting a route.",
        ),
    ).toBeInTheDocument();
});
