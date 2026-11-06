import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import ScenarioEditor from "./ScenarioEditor";
import { config, run, scenario } from "./test-fixtures";
import type { Disruption } from "./types";

it("clears invalid disruption targets when removing a location or changing its kind", () => {
    const disruption: Disruption = {
        id: "closure",
        kind: "road_closure",
        name: "Closure",
        route_id: "route-1",
        location_id: null,
        delay_minutes: 0,
        severity: 0,
        fuel_price_per_liter: null,
        enabled: true,
    };
    const facility: Disruption = {
        ...disruption,
        id: "facility",
        kind: "facility_delay",
        route_id: null,
        location_id: "supplier-1",
        delay_minutes: 15,
    };
    const weather: Disruption = {
        ...disruption,
        id: "weather",
        kind: "weather",
        route_id: null,
        severity: 0.5,
    };
    const onChange = vi.fn();
    render(
        <ScenarioEditor
            scenario={{
                ...scenario,
                disruptions: [disruption, facility, weather],
            }}
            config={config}
            routes={run.routes}
            disabled={false}
            onChange={onChange}
        />,
    );
    fireEvent.click(
        screen.getByRole("button", { name: "Remove Chicago supply" }),
    );
    expect(onChange).toHaveBeenLastCalledWith(
        expect.objectContaining({
            locations: [scenario.locations[1]],
            disruptions: [weather],
        }),
    );
    fireEvent.change(screen.getAllByLabelText("Kind")[0], {
        target: { value: "factory" },
    });
    expect(onChange).toHaveBeenLastCalledWith(
        expect.objectContaining({ disruptions: [facility, weather] }),
    );
});
