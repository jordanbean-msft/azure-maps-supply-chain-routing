import { useState } from "react";
import {
    Badge,
    Button,
    Field,
    Input,
    Select,
} from "@fluentui/react-components";
import type { MapTarget } from "./mapTarget";
import type {
    Disruption,
    OptimizationRun,
    RouteCandidate,
    Scenario,
} from "./types";

interface Props {
    scenario: Scenario;
    result: OptimizationRun | null;
    kind: Disruption["kind"];
    onKindChange: (kind: Disruption["kind"]) => void;
    target: MapTarget | null;
    onTargetChange: (target: MapTarget | null) => void;
    disabled: boolean;
    onAdd: (disruption: Disruption) => Promise<void>;
    onRemove: (id: string) => Promise<void>;
}

export default function DisruptionEditor({
    scenario,
    result,
    kind,
    onKindChange,
    target,
    onTargetChange,
    disabled,
    onAdd,
    onRemove,
}: Props) {
    const [value, setValue] = useState(30);
    const [name, setName] = useState("");
    const [error, setError] = useState<string | null>(null);
    const routes = result?.routes ?? [];
    const locationName = (id: string) =>
        scenario.locations.find((location) => location.id === id)?.name ?? id;
    const laneName = (route: RouteCandidate) =>
        `${locationName(route.supplier_id)} → ${locationName(route.factory_id)}`;
    const routeLabel = (route: RouteCandidate) => {
        const alternatives = routes.filter(
            (item) =>
                item.supplier_id === route.supplier_id &&
                item.factory_id === route.factory_id,
        );
        return `${laneName(route)} · option ${alternatives.findIndex((item) => item.id === route.id) + 1} · ${Math.round(route.distance_km)} km · ${Math.round(route.duration_minutes)} min`;
    };
    const route =
        target?.kind === "route"
            ? routes.find((item) => item.id === target.id)
            : undefined;
    const facility =
        target?.kind === "facility"
            ? scenario.locations.find((item) => item.id === target.id)
            : undefined;
    const global = kind === "weather" || kind === "fuel_price";
    const validTarget =
        kind === "road_closure"
            ? !!route
            : kind === "facility_delay"
              ? !!facility
              : target?.kind === "network";
    const description = global
        ? `Entire network · ${scenario.name}`
        : kind === "road_closure" && route
          ? routeLabel(route)
          : kind === "facility_delay" && facility
            ? `${facility.name} · ${facility.kind} · ${facility.address}`
            : "No target selected";

    const submit = async () => {
        if (!validTarget) {
            setError(
                `Choose a valid target: ${kind === "road_closure" ? "a route to close" : "a facility to delay"}.`,
            );
            return;
        }
        if (
            !Number.isFinite(value) ||
            (kind === "weather"
                ? value < 0 || value > 1
                : kind === "fuel_price"
                  ? value < 0
                  : kind === "facility_delay" && value <= 0)
        ) {
            setError(
                kind === "weather"
                    ? "Weather severity must be between 0 and 1."
                    : "Enter a positive value.",
            );
            return;
        }
        setError(null);
        try {
            await onAdd({
                id: crypto.randomUUID(),
                kind,
                name:
                    name.trim() ||
                    (kind === "road_closure"
                        ? `Closure: ${laneName(route!)}`
                        : kind === "facility_delay"
                          ? `Delay: ${facility!.name}`
                          : kind.replaceAll("_", " ")),
                route_id: kind === "road_closure" ? route!.id : null,
                location_id: kind === "facility_delay" ? facility!.id : null,
                delay_minutes: kind === "facility_delay" ? value : 0,
                severity: kind === "weather" ? value : 0,
                fuel_price_per_liter: kind === "fuel_price" ? value : null,
                enabled: true,
            });
        } catch {
            setError(
                "The disruption could not be applied. Your selection is unchanged.",
            );
        }
    };

    return (
        <section
            className="disruption-panel"
            aria-labelledby="disruption-title"
        >
            <div className="section-heading">
                <h2 id="disruption-title">Test a disruption</h2>
                <Badge appearance="tint" color="warning">
                    Simulated
                </Badge>
            </div>
            <p className="muted">
                Choose what changes and where it applies. Preview the target on
                the map before applying, then optimize again.
            </p>
            <fieldset disabled={disabled} className="disruption-fields">
                <legend className="sr-only">New disruption</legend>
                <Field label="Disruption kind">
                    <Select
                        value={kind}
                        onChange={(event) => {
                            const next = event.target
                                .value as Disruption["kind"];
                            onKindChange(next);
                            setValue(
                                next === "weather"
                                    ? 0.6
                                    : next === "fuel_price"
                                      ? 1.8
                                      : 30,
                            );
                            setError(null);
                        }}
                    >
                        <option value="road_closure">Close a route</option>
                        <option value="facility_delay">Delay a facility</option>
                        <option value="weather">
                            Network weather severity
                        </option>
                        <option value="fuel_price">Network fuel price</option>
                    </Select>
                </Field>
                {!global && (
                    <Field
                        label={
                            kind === "road_closure"
                                ? "Route to close"
                                : "Facility to delay"
                        }
                    >
                        <Select
                            value={
                                kind === "road_closure"
                                    ? (route?.id ?? "")
                                    : (facility?.id ?? "")
                            }
                            onChange={(event) =>
                                onTargetChange(
                                    event.target.value
                                        ? {
                                              kind:
                                                  kind === "road_closure"
                                                      ? "route"
                                                      : "facility",
                                              id: event.target.value,
                                          }
                                        : null,
                                )
                            }
                        >
                            <option value="">Select on the map or here</option>
                            {kind === "road_closure"
                                ? routes.map((item) => (
                                      <option value={item.id} key={item.id}>
                                          {routeLabel(item)}
                                      </option>
                                  ))
                                : scenario.locations.map((item) => (
                                      <option value={item.id} key={item.id}>
                                          {item.name} · {item.kind}
                                      </option>
                                  ))}
                        </Select>
                    </Field>
                )}
                <div
                    className={`target-preview ${validTarget ? "has-target" : ""}`}
                    role="status"
                    aria-label="Disruption target preview"
                >
                    <strong>{description}</strong>
                    <p>
                        {global
                            ? "Applies to all routes, not an individual facility. The map highlights the network."
                            : kind === "road_closure"
                              ? route
                                  ? "This candidate is outlined on the map. Only this route option is excluded; other options in the lane remain available."
                                  : "Click a route line on the map, select a row below the map, or choose a named route above."
                              : facility
                                ? `This facility is outlined on the map. The delay affects every route connected to ${facility.name}.`
                                : "Click a supplier or factory marker, or choose a named facility above."}
                    </p>
                </div>
                {kind === "road_closure" && !routes.length && (
                    <p className="muted">
                        Optimize first to generate selectable route options.
                    </p>
                )}
                <Field label="Disruption name">
                    <Input
                        value={name}
                        maxLength={120}
                        placeholder="Optional description"
                        onChange={(_, data) => setName(data.value)}
                    />
                </Field>
                {kind !== "road_closure" && (
                    <Field
                        label={
                            kind === "facility_delay"
                                ? "Delay (minutes)"
                                : kind === "weather"
                                  ? "Weather severity (0–1, all routes)"
                                  : `Fuel price (${scenario.cost_profile.currency}/liter)`
                        }
                    >
                        <Input
                            type="number"
                            step="any"
                            min={kind === "facility_delay" ? 0.01 : 0}
                            max={kind === "weather" ? 1 : undefined}
                            value={String(value)}
                            onChange={(_, data) => setValue(Number(data.value))}
                        />
                    </Field>
                )}
                <Button
                    appearance="primary"
                    disabled={disabled}
                    onClick={() => void submit()}
                >
                    Apply disruption
                </Button>
            </fieldset>
            {error && <p role="alert">{error}</p>}
            <h3 className="applied-heading">Applied disruptions</h3>
            {!scenario.disruptions.length && (
                <p className="muted">No disruptions applied.</p>
            )}
            <ul className="disruption-list">
                {scenario.disruptions.map((item) => {
                    const appliedRoute = routes.find(
                        (candidate) => candidate.id === item.route_id,
                    );
                    const scope =
                        item.kind === "facility_delay" && item.location_id
                            ? `${locationName(item.location_id)} · ${item.delay_minutes} min`
                            : item.kind === "road_closure"
                              ? appliedRoute
                                  ? routeLabel(appliedRoute)
                                  : "Previously selected route · excluded from the current plan"
                              : "Entire network";
                    return (
                        <li key={item.id}>
                            <div>
                                <strong>{item.name}</strong>
                                <span>{scope}</span>
                                {!item.enabled && <span>Disabled</span>}
                            </div>
                            <Button
                                appearance="subtle"
                                disabled={disabled}
                                onClick={() =>
                                    void onRemove(item.id).catch(() =>
                                        setError(
                                            "The disruption could not be removed.",
                                        ),
                                    )
                                }
                                aria-label={`Remove disruption ${item.name}`}
                            >
                                Remove
                            </Button>
                        </li>
                    );
                })}
            </ul>
        </section>
    );
}
