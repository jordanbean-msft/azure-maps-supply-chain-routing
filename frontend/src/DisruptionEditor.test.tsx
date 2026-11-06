import { useState } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import DisruptionEditor from "./DisruptionEditor";
import type { MapTarget } from "./mapTarget";
import { run, scenario } from "./test-fixtures";
import type { Disruption } from "./types";

function Editor({ add }: { add: (value: Disruption) => Promise<void> }) {
    const [kind, setKind] = useState<Disruption["kind"]>("road_closure");
    const [target, setTarget] = useState<MapTarget | null>(null);
    return (
        <DisruptionEditor
            scenario={scenario}
            result={run}
            kind={kind}
            onKindChange={(next) => {
                setKind(next);
                setTarget(
                    next === "weather" || next === "fuel_price"
                        ? { kind: "network", id: null }
                        : null,
                );
            }}
            target={target}
            onTargetChange={setTarget}
            disabled={false}
            onAdd={add}
            onRemove={vi.fn().mockResolvedValue(undefined)}
        />
    );
}

it("previews a named route before applying exactly that candidate closure", async () => {
    const add = vi.fn().mockResolvedValue(undefined);
    render(<Editor add={add} />);
    fireEvent.click(screen.getByRole("button", { name: "Apply disruption" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
        "Choose a valid target",
    );
    expect(add).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Route to close"), {
        target: { value: "route-2" },
    });
    expect(
        screen.getByRole("status", { name: "Disruption target preview" }),
    ).toHaveTextContent("Houston supply → Baytown factory · option 2");
    fireEvent.click(screen.getByRole("button", { name: "Apply disruption" }));
    await waitFor(() =>
        expect(add).toHaveBeenCalledWith(
            expect.objectContaining({
                kind: "road_closure",
                route_id: "route-2",
                location_id: null,
            }),
        ),
    );
});

it("clears incompatible targets and names the delayed facility and connected-route scope", async () => {
    const add = vi.fn().mockResolvedValue(undefined);
    render(<Editor add={add} />);
    fireEvent.change(screen.getByLabelText("Route to close"), {
        target: { value: "route-1" },
    });
    fireEvent.change(screen.getByLabelText("Disruption kind"), {
        target: { value: "facility_delay" },
    });
    expect(screen.getByLabelText("Facility to delay")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Facility to delay"), {
        target: { value: scenario.locations[0].id },
    });
    fireEvent.change(screen.getByLabelText("Delay (minutes)"), {
        target: { value: "45" },
    });
    expect(
        screen.getByRole("status", { name: "Disruption target preview" }),
    ).toHaveTextContent("every route connected to Houston supply");
    fireEvent.click(screen.getByRole("button", { name: "Apply disruption" }));
    await waitFor(() =>
        expect(add).toHaveBeenCalledWith(
            expect.objectContaining({
                kind: "facility_delay",
                route_id: null,
                location_id: scenario.locations[0].id,
                delay_minutes: 45,
            }),
        ),
    );
});

it("makes weather and fuel explicitly network-wide without leaking prior route targets", async () => {
    const add = vi.fn().mockResolvedValue(undefined);
    render(<Editor add={add} />);
    fireEvent.change(screen.getByLabelText("Route to close"), {
        target: { value: "route-1" },
    });
    fireEvent.change(screen.getByLabelText("Disruption kind"), {
        target: { value: "weather" },
    });
    expect(screen.queryByLabelText("Route to close")).not.toBeInTheDocument();
    expect(
        screen.getByRole("status", { name: "Disruption target preview" }),
    ).toHaveTextContent("Entire network");
    fireEvent.change(
        screen.getByLabelText("Weather severity (0–1, all routes)"),
        { target: { value: "1.5" } },
    );
    fireEvent.click(screen.getByRole("button", { name: "Apply disruption" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
        "between 0 and 1",
    );
    expect(add).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Disruption kind"), {
        target: { value: "fuel_price" },
    });
    fireEvent.change(screen.getByLabelText("Fuel price (USD/liter)"), {
        target: { value: "0" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply disruption" }));
    await waitFor(() =>
        expect(add).toHaveBeenCalledWith(
            expect.objectContaining({
                kind: "fuel_price",
                route_id: null,
                location_id: null,
                fuel_price_per_liter: 0,
            }),
        ),
    );
});

it("preserves the visible selection when applying fails", async () => {
    render(<Editor add={vi.fn().mockRejectedValue(new Error("offline"))} />);
    fireEvent.change(screen.getByLabelText("Route to close"), {
        target: { value: "route-1" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Apply disruption" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
        "Your selection is unchanged",
    );
    expect(screen.getByLabelText("Route to close")).toHaveValue("route-1");
});
