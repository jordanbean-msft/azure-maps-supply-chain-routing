import { useState } from "react";
import type { Disruption, OptimizationRun, Scenario } from "./types";

interface Props {
    scenario: Scenario;
    result: OptimizationRun | null;
    disabled: boolean;
    onAdd: (disruption: Disruption) => Promise<void>;
    onRemove: (id: string) => Promise<void>;
}

export default function DisruptionEditor({
    scenario,
    result,
    disabled,
    onAdd,
    onRemove,
}: Props) {
    const [kind, setKind] = useState<Disruption["kind"]>("road_closure");
    const [target, setTarget] = useState("");
    const [value, setValue] = useState(30);
    const [name, setName] = useState("");
    const [error, setError] = useState<string | null>(null);
    const routeTargets = result?.routes ?? [];
    const validTarget =
        kind === "road_closure"
            ? routeTargets.some((item) => item.id === target)
            : kind === "facility_delay"
              ? scenario.locations.some((item) => item.id === target)
              : true;

    const submit = async () => {
        if (!validTarget) {
            setError("Choose a valid target for this disruption.");
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
        await onAdd({
            id: crypto.randomUUID(),
            kind,
            name: name.trim() || kind.replaceAll("_", " "),
            route_id: kind === "road_closure" ? target : null,
            location_id: kind === "facility_delay" ? target : null,
            delay_minutes: kind === "facility_delay" ? value : 0,
            severity: kind === "weather" ? value : 0,
            fuel_price_per_liter: kind === "fuel_price" ? value : null,
            enabled: true,
        });
    };
    return (
        <section
            className="panel disruption-panel"
            aria-labelledby="disruption-title"
        >
            <div className="panel-heading">
                <div>
                    <p className="eyebrow">WHAT IF</p>
                    <h2 id="disruption-title">Stress-test the network</h2>
                </div>
                <span className="badge amber">Simulated inputs</span>
            </div>
            <p className="muted">
                Apply an assumption, then optimize again to compare costs.
                Closures exclude a candidate route, not every road in its lane.
            </p>
            <fieldset disabled={disabled} className="disruption-fields">
                <legend className="sr-only">New disruption</legend>
                <label>
                    Disruption kind
                    <select
                        value={kind}
                        onChange={(e) => {
                            const next = e.target.value as Disruption["kind"];
                            setKind(next);
                            setTarget("");
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
                        <option value="road_closure">Road closure</option>
                        <option value="facility_delay">Facility delay</option>
                        <option value="weather">Weather severity</option>
                        <option value="fuel_price">Fuel price override</option>
                    </select>
                </label>
                <label>
                    Disruption name
                    <input
                        value={name}
                        maxLength={120}
                        placeholder="Optional description"
                        onChange={(e) => setName(e.target.value)}
                    />
                </label>
                {(kind === "road_closure" || kind === "facility_delay") && (
                    <label>
                        Target
                        <select
                            value={target}
                            onChange={(e) => setTarget(e.target.value)}
                        >
                            <option value="">
                                Choose{" "}
                                {kind === "road_closure"
                                    ? "a route"
                                    : "a facility"}
                            </option>
                            {kind === "road_closure"
                                ? routeTargets.map((route) => (
                                      <option value={route.id} key={route.id}>
                                          {route.id}
                                      </option>
                                  ))
                                : scenario.locations.map((location) => (
                                      <option
                                          value={location.id}
                                          key={location.id}
                                      >
                                          {location.name}
                                      </option>
                                  ))}
                        </select>
                    </label>
                )}
                {kind !== "road_closure" && (
                    <label>
                        {kind === "facility_delay"
                            ? "Delay (minutes)"
                            : kind === "weather"
                              ? "Weather severity (0–1, all routes)"
                              : `Fuel price (${scenario.cost_profile.currency}/liter)`}
                        <input
                            type="number"
                            step="any"
                            min={kind === "facility_delay" ? 0.01 : 0}
                            max={kind === "weather" ? 1 : undefined}
                            value={value}
                            onChange={(e) => setValue(Number(e.target.value))}
                        />
                    </label>
                )}
                <button
                    type="button"
                    className="primary"
                    onClick={() => void submit()}
                >
                    Apply disruption
                </button>
            </fieldset>
            {kind === "road_closure" && !routeTargets.length && (
                <p className="muted">
                    Optimize first to get selectable route targets.
                </p>
            )}
            {error && (
                <p role="alert" className="inline-error">
                    {error}
                </p>
            )}
            <ul className="disruption-list">
                {scenario.disruptions.map((item) => (
                    <li key={item.id}>
                        <span>
                            <strong>{item.name}</strong> ·{" "}
                            {item.kind.replaceAll("_", " ")}
                            {!item.enabled ? " (disabled)" : ""}
                        </span>
                        <button
                            disabled={disabled}
                            type="button"
                            className="quiet"
                            onClick={() => void onRemove(item.id)}
                            aria-label={`Remove disruption ${item.name}`}
                        >
                            Remove
                        </button>
                    </li>
                ))}
            </ul>
        </section>
    );
}
