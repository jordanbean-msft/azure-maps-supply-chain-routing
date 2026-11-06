import { useCallback, useEffect, useState } from "react";
import {
    Badge,
    Button,
    Checkbox,
    Field,
    MessageBar,
    MessageBarBody,
    ProgressBar,
    Select,
    Tab,
    TabList,
} from "@fluentui/react-components";
import { ArrowClockwiseRegular, PlayRegular } from "@fluentui/react-icons";
import DisruptionEditor from "./DisruptionEditor";
import MapView from "./MapView";
import RouteResults from "./RouteResults";
import ScenarioEditor from "./ScenarioEditor";
import type { MapTarget } from "./mapTarget";
import { useWorkspace } from "./useWorkspace";
import type { Allocation, Disruption, Location, RouteCandidate } from "./types";
import "./style.css";

const noRoutes: RouteCandidate[] = [];
const noLocations: Location[] = [];
const noAllocations: Allocation[] = [];

export default function App() {
    const workspace = useWorkspace();
    const [selected, setSelected] = useState<string | null>(null);
    const [selectedLocation, setSelectedLocation] = useState<string | null>(
        null,
    );
    const [target, setTarget] = useState<MapTarget | null>(null);
    const [disruptionKind, setDisruptionKind] =
        useState<Disruption["kind"]>("road_closure");
    const [tab, setTab] = useState("network");
    const [refreshSeconds, setRefreshSeconds] = useState(60);
    const [paused, setPaused] = useState(false);
    const running =
        workspace.run?.status === "queued" ||
        workspace.run?.status === "running";
    const locked = workspace.busy || running;
    const { refresh, scenario, edit } = workspace;
    const routes = workspace.result?.routes ?? noRoutes;
    const selectedId = routes.some((route) => route.id === selected)
        ? selected
        : null;
    const facilityId = scenario?.locations.some(
        (location) => location.id === selectedLocation,
    )
        ? selectedLocation
        : null;
    const validTarget =
        target?.kind === "network" ||
        (target?.kind === "route" &&
            routes.some((route) => route.id === target.id)) ||
        (target?.kind === "facility" &&
            scenario?.locations.some((location) => location.id === target.id))
            ? target
            : null;

    const move = useCallback(
        (location: Location) => {
            if (scenario)
                edit({
                    ...scenario,
                    locations: scenario.locations.map((item) =>
                        item.id === location.id ? location : item,
                    ),
                });
        },
        [scenario, edit],
    );
    const selectRoute = useCallback(
        (id: string) => {
            setSelected(id);
            setSelectedLocation(null);
            if (tab === "disruptions" && disruptionKind === "road_closure")
                setTarget({ kind: "route", id });
        },
        [disruptionKind, tab],
    );
    const selectLocation = useCallback(
        (id: string) => {
            setSelectedLocation(id);
            if (tab === "disruptions" && disruptionKind === "facility_delay")
                setTarget({ kind: "facility", id });
        },
        [disruptionKind, tab],
    );
    const chooseTarget = (next: MapTarget | null) => {
        setTarget(next);
        if (next?.kind === "route") {
            setSelected(next.id);
            setSelectedLocation(null);
        }
        if (next?.kind === "facility") setSelectedLocation(next.id);
    };
    const changeKind = (kind: Disruption["kind"]) => {
        setDisruptionKind(kind);
        setTarget(
            kind === "weather" || kind === "fuel_price"
                ? { kind: "network", id: null }
                : kind === "road_closure" && selectedId
                  ? { kind: "route", id: selectedId }
                  : kind === "facility_delay" && facilityId
                    ? { kind: "facility", id: facilityId }
                    : null,
        );
    };

    useEffect(() => {
        if (paused || !scenario || refreshSeconds < 30) return;
        const interval = window.setInterval(() => {
            if (document.visibilityState === "visible")
                void refresh(false, true);
        }, refreshSeconds * 1000);
        return () => window.clearInterval(interval);
    }, [paused, scenario?.id, refreshSeconds, refresh, scenario]);

    return (
        <main className="app-shell" id="main-content">
            <section
                className="workspace-toolbar"
                aria-label="Scenario actions"
            >
                <div className="scenario-heading">
                    <h1>{scenario?.name ?? "Houston supply network"}</h1>
                    {scenario && (
                        <Badge
                            appearance="tint"
                            color={workspace.dirty ? "warning" : "subtle"}
                        >
                            {workspace.dirty ? "Unsaved edits" : "Saved"}
                        </Badge>
                    )}
                </div>
                <div className="actions">
                    <Button
                        disabled={
                            !workspace.config || locked || workspace.dirty
                        }
                        onClick={() => {
                            setSelected(null);
                            setSelectedLocation(null);
                            setTarget(null);
                            setDisruptionKind("road_closure");
                            setTab("network");
                            void workspace.seed();
                        }}
                    >
                        Load Houston sample
                    </Button>
                    {scenario && (
                        <>
                            <Button
                                type="submit"
                                form="scenario-form"
                                disabled={!workspace.dirty || locked}
                            >
                                Save changes
                            </Button>
                            <Button
                                icon={<ArrowClockwiseRegular />}
                                disabled={locked}
                                onClick={() => void refresh(true)}
                            >
                                {workspace.dirty
                                    ? "Discard edits & reload"
                                    : "Reload server version"}
                            </Button>
                            <Button
                                appearance="primary"
                                icon={<PlayRegular />}
                                aria-describedby="shipment-plan-explanation"
                                disabled={
                                    locked ||
                                    workspace.dirty ||
                                    !workspace.config?.routing_available
                                }
                                onClick={() => void workspace.optimize()}
                            >
                                {running
                                    ? "Calculating plan…"
                                    : "Calculate shipment plan"}
                            </Button>
                        </>
                    )}
                </div>
            </section>

            <p id="shipment-plan-explanation" className="planning-explanation">
                <strong>What this calculates:</strong> the lowest estimated
                total-cost way to send all supplier supply to factories without
                exceeding factory capacities. It compares available routes using
                traffic, weather, your costs and simulated disruptions. This is
                a shipment allocation, not a single fastest route or a truck
                dispatch schedule.
            </p>
            <div className="workspace-status">
                <span role="status">
                    {!workspace.config
                        ? "Connecting to API…"
                        : workspace.config.mode === "demo"
                          ? "SIMULATION MODE · No live traffic or weather. Scenarios use temporary memory."
                          : `LIVE MODE · Azure Maps ${workspace.config.maps_available ? "available" : "unavailable"}. Weather delays and tolls are estimates.`}
                </span>
                {workspace.lastUpdated && (
                    <span>
                        Updated{" "}
                        <time dateTime={workspace.lastUpdated}>
                            {new Date(
                                workspace.lastUpdated,
                            ).toLocaleTimeString()}
                        </time>
                    </span>
                )}
            </div>
            {workspace.error && (
                <MessageBar intent="error" role="alert">
                    <MessageBarBody>{workspace.error}</MessageBarBody>
                </MessageBar>
            )}
            {workspace.stale && (
                <MessageBar intent="warning">
                    <MessageBarBody>
                        Results may be stale. Save edits and calculate a new
                        shipment plan to update the map and costs.
                    </MessageBarBody>
                </MessageBar>
            )}
            {workspace.run && (
                <section
                    className="run-status"
                    aria-label="Optimization progress"
                    aria-live="polite"
                >
                    <span>
                        {workspace.run.status.toUpperCase()} ·{" "}
                        {workspace.run.stage.replaceAll("_", " ")}
                    </span>
                    <ProgressBar
                        value={workspace.run.progress}
                        aria-label="Optimization completion"
                    />
                    <span>{workspace.connection}</span>
                </section>
            )}

            <div className="planning-grid">
                <aside
                    className="planning-sidebar"
                    aria-label="Planning controls"
                >
                    {scenario && workspace.config ? (
                        <>
                            <TabList
                                selectedValue={tab}
                                onTabSelect={(_, data) =>
                                    setTab(String(data.value))
                                }
                                aria-label="Planning tools"
                            >
                                <Tab value="network">Network</Tab>
                                <Tab value="disruptions">Disruptions</Tab>
                            </TabList>
                            <div
                                hidden={tab !== "network"}
                                className="sidebar-content"
                            >
                                <form
                                    id="scenario-form"
                                    onSubmit={(event) => {
                                        event.preventDefault();
                                        void workspace.save();
                                    }}
                                >
                                    <ScenarioEditor
                                        scenario={scenario}
                                        config={workspace.config}
                                        disabled={locked}
                                        routes={routes}
                                        onChange={workspace.edit}
                                        onSelectLocation={selectLocation}
                                        selectedLocation={facilityId}
                                    />
                                    <Button
                                        appearance="primary"
                                        className="editor-save"
                                        type="submit"
                                        disabled={!workspace.dirty || locked}
                                    >
                                        Save scenario
                                    </Button>
                                </form>
                            </div>
                            <div
                                hidden={tab !== "disruptions"}
                                className="sidebar-content"
                            >
                                <DisruptionEditor
                                    scenario={scenario}
                                    result={workspace.result}
                                    kind={disruptionKind}
                                    onKindChange={changeKind}
                                    target={validTarget}
                                    onTargetChange={chooseTarget}
                                    disabled={locked || workspace.dirty}
                                    onAdd={workspace.addDisruption}
                                    onRemove={workspace.removeDisruption}
                                />
                            </div>
                            <details className="refresh-settings">
                                <summary>Refresh settings</summary>
                                <Field label="Refresh interval">
                                    <Select
                                        value={refreshSeconds}
                                        onChange={(event) =>
                                            setRefreshSeconds(
                                                Number(event.target.value),
                                            )
                                        }
                                    >
                                        <option value={60}>60 seconds</option>
                                        <option value={120}>2 minutes</option>
                                        <option value={300}>5 minutes</option>
                                    </Select>
                                </Field>
                                <Checkbox
                                    label="Pause auto-refresh"
                                    checked={paused}
                                    onChange={(_, data) =>
                                        setPaused(data.checked === true)
                                    }
                                />
                                <Button
                                    disabled={locked || workspace.dirty}
                                    onClick={() => void refresh(false, true)}
                                >
                                    Refresh & recalculate plan
                                </Button>
                                <p className="muted">
                                    {workspace.dirty
                                        ? "Refresh paused to protect unsaved edits."
                                        : running
                                          ? "Refresh waits for the active run."
                                          : "Visible tabs only. Live requests may incur Azure charges."}
                                </p>
                            </details>
                        </>
                    ) : (
                        <div className="sidebar-content">
                            <h2>Start with Houston</h2>
                            <p>
                                Load the Houston sample to plan shipments
                                between suppliers and factories around the metro
                                area.
                            </p>
                            <p className="muted">
                                Inspect facilities and routes on the map. Edit
                                capacity, compare costs, then test a closure or
                                delay at a specific location.
                            </p>
                        </div>
                    )}
                </aside>
                <div className="analysis-column">
                    <MapView
                        mapsAvailable={
                            workspace.config?.maps_available ?? false
                        }
                        locations={scenario?.locations ?? noLocations}
                        routes={routes}
                        allocations={
                            workspace.result?.allocations ?? noAllocations
                        }
                        selected={selectedId}
                        selectedLocation={facilityId}
                        target={tab === "disruptions" ? validTarget : null}
                        disruptions={scenario?.disruptions}
                        disabled={locked || !scenario}
                        onSelect={selectRoute}
                        onSelectLocation={selectLocation}
                        onMove={move}
                    />
                    {scenario && (
                        <RouteResults
                            scenario={workspace.resultScenario ?? scenario}
                            result={workspace.result}
                            previous={workspace.previous}
                            selected={selectedId}
                            onSelect={selectRoute}
                            stale={workspace.stale}
                        />
                    )}
                </div>
            </div>
            <footer>
                Lane planning, not fleet dispatch. Costs, tolls and weather
                delays are estimates. Disruptions are simulated.
            </footer>
        </main>
    );
}
