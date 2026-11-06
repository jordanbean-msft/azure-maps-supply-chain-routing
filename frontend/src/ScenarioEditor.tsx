import { Button, Input, Select } from "@fluentui/react-components";
import { useEffect, useRef, useState } from "react";
import { errorMessage, request, scenarioPath } from "./api";
import type {
    AppConfig,
    GeocodeResult,
    Location,
    RouteCandidate,
    Scenario,
} from "./types";

interface Props {
    scenario: Scenario;
    config: AppConfig;
    disabled: boolean;
    routes: RouteCandidate[];
    onChange: (scenario: Scenario) => void;
    selectedLocation?: string | null;
    onSelectLocation?: (id: string) => void;
}

const humanize = (value: string) => value.replaceAll("_", " ");

function LocationEditor({
    location,
    scenarioId,
    onChange,
    onRemove,
    selected,
    onSelect,
}: {
    location: Location;
    scenarioId: string;
    onChange: (location: Location) => void;
    onRemove: () => void;
    selected?: boolean;
    onSelect?: () => void;
}) {
    const [results, setResults] = useState<GeocodeResult[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [searching, setSearching] = useState(false);
    const search = useRef<AbortController | null>(null);
    useEffect(() => () => search.current?.abort(), []);

    const geocode = async () => {
        search.current?.abort();
        const controller = new AbortController();
        search.current = controller;
        setSearching(true);
        setError(null);
        setResults([]);
        try {
            const { data } = await request<GeocodeResult[]>(
                `${scenarioPath(scenarioId)}/locations:geocode`,
                {
                    method: "POST",
                    body: JSON.stringify({ address: location.address }),
                    signal: controller.signal,
                },
            );
            if (!controller.signal.aborted) {
                setResults(data);
                if (!data.length)
                    setError(
                        "No matching addresses. Enter coordinates manually.",
                    );
            }
        } catch (failure) {
            if (!controller.signal.aborted) setError(errorMessage(failure));
        } finally {
            if (!controller.signal.aborted) setSearching(false);
        }
    };

    return (
        <fieldset
            className={`location-card${selected ? " location-selected" : ""}`}
        >
            <legend>
                {location.kind === "supplier"
                    ? "Supplier supply"
                    : "Factory capacity"}{" "}
                · {location.name || "New location"}
            </legend>
            <div className="fields">
                <label>
                    Name
                    <Input
                        value={location.name}
                        required
                        maxLength={120}
                        onChange={(e) =>
                            onChange({ ...location, name: e.target.value })
                        }
                    />
                </label>
                <label>
                    Kind
                    <Select
                        value={location.kind}
                        onChange={(e) =>
                            onChange({
                                ...location,
                                kind: e.target.value as Location["kind"],
                            })
                        }
                    >
                        <option value="supplier">Supplier</option>
                        <option value="factory">Factory</option>
                    </Select>
                </label>
                <label className="wide">
                    Address
                    <Input
                        value={location.address}
                        maxLength={500}
                        onChange={(e) => {
                            search.current?.abort();
                            setSearching(false);
                            setResults([]);
                            onChange({ ...location, address: e.target.value });
                        }}
                    />
                </label>
                <label>
                    Latitude
                    <Input
                        type="number"
                        step="any"
                        min={24}
                        max={50}
                        required
                        value={String(location.latitude)}
                        onChange={(e) =>
                            onChange({
                                ...location,
                                latitude: Number(e.target.value),
                            })
                        }
                    />
                </label>
                <label>
                    Longitude
                    <Input
                        type="number"
                        step="any"
                        min={-125}
                        max={-66}
                        required
                        value={String(location.longitude)}
                        onChange={(e) =>
                            onChange({
                                ...location,
                                longitude: Number(e.target.value),
                            })
                        }
                    />
                </label>
                <label>
                    {location.kind === "supplier"
                        ? "Supply (units)"
                        : "Capacity (units)"}
                    <Input
                        type="number"
                        min={0}
                        max={100000}
                        step={0.001}
                        required
                        value={String(location.quantity)}
                        onChange={(e) =>
                            onChange({
                                ...location,
                                quantity: Number(e.target.value),
                            })
                        }
                    />
                </label>
            </div>
            <div className="actions">
                {onSelect && (
                    <Button
                        type="button"
                        appearance="subtle"
                        onClick={onSelect}
                        aria-label={`Select ${location.name} on map`}
                        aria-pressed={selected}
                    >
                        Select on map
                    </Button>
                )}
                <Button
                    type="button"
                    onClick={() => void geocode()}
                    disabled={!location.address.trim() || searching}
                >
                    {searching ? "Finding…" : "Find address"}
                </Button>
                <Button
                    type="button"
                    appearance="subtle"
                    className="danger"
                    onClick={onRemove}
                    aria-label={`Remove ${location.name || "location"}`}
                >
                    Remove
                </Button>
            </div>
            {error && (
                <p role="alert" className="inline-error">
                    {error}
                </p>
            )}
            {results.length > 0 && (
                <fieldset className="geocode-results">
                    <legend>Choose an address match</legend>
                    {results.map((result, index) => (
                        <Button
                            type="button"
                            key={index}
                            onClick={() => {
                                onChange({ ...location, ...result });
                                setResults([]);
                            }}
                        >
                            {result.address} ({result.latitude.toFixed(4)},{" "}
                            {result.longitude.toFixed(4)})
                        </Button>
                    ))}
                </fieldset>
            )}
        </fieldset>
    );
}

export default function ScenarioEditor({
    scenario,
    config,
    disabled,
    routes,
    onChange,
    selectedLocation,
    onSelectLocation,
}: Props) {
    const routeTargetsFor = (id: string) =>
        new Set(
            routes
                .filter(
                    (route) =>
                        route.supplier_id === id || route.factory_id === id,
                )
                .map((route) => route.id),
        );
    const updateLocation = (location: Location) => {
        const changedKind =
            scenario.locations.find((item) => item.id === location.id)?.kind !==
            location.kind;
        const invalidRoutes = changedKind
            ? routeTargetsFor(location.id)
            : new Set<string>();
        onChange({
            ...scenario,
            locations: scenario.locations.map((item) =>
                item.id === location.id ? location : item,
            ),
            disruptions: scenario.disruptions.filter(
                (item) => !item.route_id || !invalidRoutes.has(item.route_id),
            ),
        });
    };
    const add = (kind: Location["kind"]) =>
        onChange({
            ...scenario,
            locations: [
                ...scenario.locations,
                {
                    id: crypto.randomUUID(),
                    kind,
                    name: kind === "supplier" ? "New supplier" : "New factory",
                    address: "",
                    latitude: 29.7604,
                    longitude: -95.3698,
                    quantity: 100,
                },
            ],
        });
    // datetime-local uses local wall-clock time; persist timezone-aware ISO timestamps.
    const departure = new Date(scenario.departure_time);
    const localDeparture = Number.isNaN(departure.getTime())
        ? ""
        : new Date(departure.getTime() - departure.getTimezoneOffset() * 60000)
              .toISOString()
              .slice(0, 16);
    const suppliers = scenario.locations.filter(
        (location) => location.kind === "supplier",
    ).length;
    const factories = scenario.locations.length - suppliers;
    return (
        <fieldset disabled={disabled} className="editor-body">
            <legend className="sr-only">Scenario inputs</legend>
            <label>
                Scenario name
                <Input
                    value={scenario.name}
                    required
                    maxLength={120}
                    onChange={(e) =>
                        onChange({ ...scenario, name: e.target.value })
                    }
                />
            </label>
            <label>
                Departure time (your local timezone)
                <Input
                    type="datetime-local"
                    value={localDeparture}
                    required
                    onChange={(e) => {
                        if (e.target.value)
                            onChange({
                                ...scenario,
                                departure_time: new Date(
                                    e.target.value,
                                ).toISOString(),
                            });
                    }}
                />
            </label>
            <p className="muted">
                {suppliers}/{config.max_suppliers} suppliers · {factories}/
                {config.max_factories} factories. Contiguous-US demo bounds:
                latitude 24–50, longitude −125 to −66. New facilities start in
                Houston. Drag markers or edit coordinates to move them.
            </p>
            <p className="muted">
                Removing a location clears its facility disruptions and known
                route targets. Changing its kind clears affected route
                disruptions.
            </p>
            {scenario.locations.map((location) => (
                <LocationEditor
                    key={location.id}
                    location={location}
                    scenarioId={scenario.id}
                    selected={selectedLocation === location.id}
                    onSelect={
                        onSelectLocation
                            ? () => onSelectLocation(location.id)
                            : undefined
                    }
                    onChange={updateLocation}
                    onRemove={() =>
                        onChange({
                            ...scenario,
                            locations: scenario.locations.filter(
                                (item) => item.id !== location.id,
                            ),
                            disruptions: scenario.disruptions.filter(
                                (item) =>
                                    item.location_id !== location.id &&
                                    (!item.route_id ||
                                        !routeTargetsFor(location.id).has(
                                            item.route_id,
                                        )),
                            ),
                        })
                    }
                />
            ))}
            <div className="actions">
                <Button
                    type="button"
                    disabled={suppliers >= config.max_suppliers}
                    onClick={() => add("supplier")}
                >
                    + Supplier
                </Button>
                <Button
                    type="button"
                    disabled={factories >= config.max_factories}
                    onClick={() => add("factory")}
                >
                    + Factory
                </Button>
            </div>
            {(suppliers > config.max_suppliers ||
                factories > config.max_factories) && (
                <p role="alert">
                    Location kind exceeds the configured limit. Change the kind
                    or remove a location.
                </p>
            )}
            <details>
                <summary>Truck routing assumptions</summary>
                <p className="muted">
                    Lane planning only; not fleet dispatch or multi-truck
                    packing.
                </p>
                <div className="fields">
                    {(
                        Object.keys(
                            scenario.truck,
                        ) as (keyof Scenario["truck"])[]
                    ).map((key) => (
                        <label key={key}>
                            {humanize(key)}
                            <Input
                                type="number"
                                min={0.01}
                                step="any"
                                required
                                value={String(scenario.truck[key])}
                                onChange={(e) =>
                                    onChange({
                                        ...scenario,
                                        truck: {
                                            ...scenario.truck,
                                            [key]: Number(e.target.value),
                                        },
                                    })
                                }
                            />
                        </label>
                    ))}
                </div>
            </details>
            <details>
                <summary>Cost assumptions · all rates editable</summary>
                <p className="muted">
                    Estimated business costs, not Azure guarantees. Driver time
                    includes weather and simulated delays. Traffic is already
                    included in drive time; traffic penalty is an additional
                    business penalty.
                </p>
                <label>
                    Currency (ISO code)
                    <Select
                        value={scenario.cost_profile.currency}
                        onChange={(e) =>
                            onChange({
                                ...scenario,
                                cost_profile: {
                                    ...scenario.cost_profile,
                                    currency: e.target.value,
                                },
                            })
                        }
                    >
                        {["USD", "CAD", "EUR", "GBP"].map((currency) => (
                            <option key={currency}>{currency}</option>
                        ))}
                    </Select>
                </label>
                <div className="fields">
                    {(
                        Object.keys(
                            scenario.cost_profile,
                        ) as (keyof Scenario["cost_profile"])[]
                    )
                        .filter((key) => key !== "currency")
                        .map((key) => (
                            <label key={key}>
                                {humanize(key)}
                                <Input
                                    type="number"
                                    min={0}
                                    step="any"
                                    required
                                    value={String(scenario.cost_profile[key])}
                                    onChange={(e) =>
                                        onChange({
                                            ...scenario,
                                            cost_profile: {
                                                ...scenario.cost_profile,
                                                [key]: Number(e.target.value),
                                            },
                                        })
                                    }
                                />
                            </label>
                        ))}
                </div>
            </details>
        </fieldset>
    );
}
