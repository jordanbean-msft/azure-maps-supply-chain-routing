import { useCallback, useEffect, useState } from "react";
import DisruptionEditor from "./DisruptionEditor";
import MapView from "./MapView";
import RouteResults from "./RouteResults";
import ScenarioEditor from "./ScenarioEditor";
import { useWorkspace } from "./useWorkspace";
import type { Location, RouteCandidate } from "./types";
import "./style.css";

const noRoutes: RouteCandidate[] = [];

export default function App() {
    const workspace = useWorkspace();
    const [selected, setSelected] = useState<string | null>(null);
    const [refreshSeconds, setRefreshSeconds] = useState(60);
    const [paused, setPaused] = useState(false);
    const running =
        workspace.run?.status === "queued" ||
        workspace.run?.status === "running";
    const locked = workspace.busy || running;
    const { refresh, scenario, edit } = workspace;
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
    useEffect(() => {
        if (paused || !scenario || refreshSeconds < 30) return;
        const interval = window.setInterval(() => {
            if (document.visibilityState === "visible")
                void refresh(false, true);
        }, refreshSeconds * 1000);
        return () => window.clearInterval(interval);
    }, [paused, scenario?.id, refreshSeconds, refresh, scenario]);
    const selectedId = workspace.result?.routes.some(
        (route) => route.id === selected,
    )
        ? selected
        : (workspace.result?.routes[0]?.id ?? null);

    return (
        <main className="app-shell">
            <header className="masthead">
                <a
                    className="brand"
                    href="#main-content"
                    aria-label="Supply Chain Routing home"
                >
                    <span className="brand-symbol" aria-hidden="true">
                        ↗
                    </span>
                    <span>
                        SUPPLY CHAIN
                        <span className="brand-sub">ROUTING LAB</span>
                    </span>
                </a>
                <div className="header-note">
                    Strategic lane planning<span>Powered by Azure Maps</span>
                </div>
            </header>
            <section className="hero" id="main-content">
                <div>
                    <p className="eyebrow">FROM SUPPLY TO POSSIBILITY</p>
                    <h1>
                        A clearer route to
                        <br />
                        <em>better decisions.</em>
                    </h1>
                    <p className="hero-copy">
                        Build your network. Compare the trade-offs. See how
                        every mile, minute, and disruption changes the plan.
                    </p>
                </div>
                <div className="hero-action">
                    <button
                        type="button"
                        className="primary large"
                        disabled={
                            !workspace.config || locked || workspace.dirty
                        }
                        onClick={() => {
                            setSelected(null);
                            void workspace.seed();
                        }}
                    >
                        Load seed scenario <span aria-hidden="true">↗</span>
                    </button>
                    <span>
                        Editable suppliers & factories · no credentials in demo
                        mode
                    </span>
                </div>
            </section>

            <div className="mode-banner" role="status">
                {!workspace.config
                    ? "Connecting to API…"
                    : workspace.config.mode === "demo"
                      ? "SIMULATION MODE — deterministic simulated routing. No live traffic or weather. In-memory scenarios can expire on restart."
                      : `LIVE MODE — Azure Maps ${workspace.config.maps_available ? "available" : "not available"}. Routing ${workspace.config.routing_available ? "available" : "unavailable"}; weather and tolls remain estimates.`}
            </div>
            {workspace.error && (
                <div role="alert" className="error-banner">
                    <strong>Action needed.</strong> {workspace.error}
                </div>
            )}
            {!scenario && (
                <section className="welcome panel">
                    <p className="eyebrow">START WITH A NETWORK</p>
                    <h2>Your next decision starts here.</h2>
                    <p>
                        Load the seed scenario above to explore editable supply,
                        factory capacity, alternate routes, and transparent
                        shipment costs.
                    </p>
                    <div className="welcome-steps">
                        <span>
                            <b>01</b> Define the network
                        </span>
                        <span>
                            <b>02</b> Optimize the lanes
                        </span>
                        <span>
                            <b>03</b> Test a disruption
                        </span>
                    </div>
                </section>
            )}
            {scenario && workspace.config && (
                <>
                    <section
                        className="workspace-toolbar"
                        aria-label="Scenario actions"
                    >
                        <div>
                            <strong>{scenario.name}</strong>
                            <span
                                className={`badge ${workspace.dirty ? "amber" : ""}`}
                            >
                                {workspace.dirty ? "Unsaved edits" : "Saved"}
                            </span>
                            <small>Scenario {scenario.id}</small>
                        </div>
                        <div className="actions">
                            <button
                                type="submit"
                                form="scenario-form"
                                disabled={!workspace.dirty || locked}
                            >
                                Save changes
                            </button>
                            <button
                                type="button"
                                disabled={locked}
                                onClick={() => void refresh(true)}
                            >
                                {workspace.dirty
                                    ? "Discard edits & reload"
                                    : "Reload server version"}
                            </button>
                            <button
                                type="button"
                                className="primary"
                                disabled={
                                    locked ||
                                    workspace.dirty ||
                                    !workspace.config.routing_available
                                }
                                onClick={() => void workspace.optimize()}
                            >
                                {running ? "Optimizing…" : "Optimize network"}
                            </button>
                        </div>
                    </section>
                    <section
                        className="refresh-bar"
                        aria-label="Live refresh controls"
                    >
                        <span>
                            Last updated:{" "}
                            <time dateTime={workspace.lastUpdated ?? undefined}>
                                {workspace.lastUpdated
                                    ? new Date(
                                          workspace.lastUpdated,
                                      ).toLocaleTimeString()
                                    : "not yet"}
                            </time>
                        </span>
                        <label>
                            Refresh interval
                            <select
                                value={refreshSeconds}
                                onChange={(e) =>
                                    setRefreshSeconds(Number(e.target.value))
                                }
                            >
                                <option value={60}>60 seconds</option>
                                <option value={120}>2 minutes</option>
                                <option value={300}>5 minutes</option>
                            </select>
                        </label>
                        <label className="checkbox">
                            <input
                                type="checkbox"
                                checked={paused}
                                onChange={(e) => setPaused(e.target.checked)}
                            />{" "}
                            Pause auto-refresh
                        </label>
                        <button
                            type="button"
                            className="quiet"
                            disabled={locked || workspace.dirty}
                            onClick={() => void refresh(false, true)}
                        >
                            Refresh & optimize now
                        </button>
                        <small>
                            {workspace.dirty
                                ? "Refresh paused to protect unsaved edits."
                                : running
                                  ? "Refresh waits for the active run."
                                  : "Visible tabs only; refresh re-optimizes saved inputs. Live requests may incur Azure charges."}
                        </small>
                    </section>
                    {workspace.stale && (
                        <p className="notice" role="status">
                            Results may be stale: inputs changed or a run is in
                            progress. Save edits and optimize to generate a
                            matching snapshot.
                        </p>
                    )}
                    {workspace.run && (
                        <section
                            className="run-status"
                            aria-label="Optimization progress"
                            aria-live="polite"
                        >
                            <div>
                                <strong>
                                    {workspace.run.status.toUpperCase()} ·{" "}
                                    {workspace.run.stage.replaceAll("_", " ")}
                                </strong>
                                <span>{workspace.connection}</span>
                            </div>
                            <progress
                                value={workspace.run.progress}
                                max={1}
                                aria-label="Optimization completion"
                            />
                            <span>
                                {Math.round(workspace.run.progress * 100)}%
                            </span>
                        </section>
                    )}
                    <div className="workspace-grid">
                        <section
                            className="panel editor-panel"
                            aria-labelledby="editor-title"
                        >
                            <div className="panel-heading">
                                <div>
                                    <p className="eyebrow">01 / DEFINE</p>
                                    <h2 id="editor-title">Your network</h2>
                                </div>
                            </div>
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
                                    routes={
                                        workspace.result?.routes ?? noRoutes
                                    }
                                    onChange={workspace.edit}
                                />
                                <button
                                    className="primary editor-save"
                                    type="submit"
                                    disabled={!workspace.dirty || locked}
                                >
                                    Save scenario
                                </button>
                            </form>
                        </section>
                        <div className="analysis-column">
                            <MapView
                                mapsAvailable={workspace.config.maps_available}
                                locations={scenario.locations}
                                routes={workspace.result?.routes ?? noRoutes}
                                selected={selectedId}
                                disabled={locked}
                                onSelect={setSelected}
                                onMove={move}
                            />
                            <DisruptionEditor
                                scenario={scenario}
                                result={workspace.result}
                                disabled={locked || workspace.dirty}
                                onAdd={workspace.addDisruption}
                                onRemove={workspace.removeDisruption}
                            />
                        </div>
                    </div>
                    <RouteResults
                        scenario={workspace.resultScenario ?? scenario}
                        result={workspace.result}
                        previous={workspace.previous}
                        selected={selectedId}
                        onSelect={setSelected}
                        stale={workspace.stale}
                    />
                </>
            )}
            <footer>
                <span>SUPPLY CHAIN ROUTING LAB</span>
                <p>
                    A bounded public demonstration, not dispatch advice.
                    Shipment unit costs are illustrative estimates. No live
                    service failure is silently replaced with simulated data.
                </p>
            </footer>
        </main>
    );
}
