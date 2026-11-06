import { useCallback, useEffect, useReducer, useRef } from "react";
import { ApiError, errorMessage, request, scenarioPath } from "./api";
import { consumeEvents } from "./eventStream";
import type {
    AppConfig,
    Disruption,
    OptimizationRun,
    RunEvent,
    Scenario,
} from "./types";

interface Workspace {
    config: AppConfig | null;
    scenario: Scenario | null;
    etag: string | null;
    dirty: boolean;
    stale: boolean;
    busy: boolean;
    error: string | null;
    run: OptimizationRun | null;
    result: OptimizationRun | null;
    resultScenario: Scenario | null;
    previous: OptimizationRun | null;
    lastUpdated: string | null;
    connection: string;
}

const initial: Workspace = {
    config: null,
    scenario: null,
    etag: null,
    dirty: false,
    stale: false,
    busy: true,
    error: null,
    run: null,
    result: null,
    resultScenario: null,
    previous: null,
    lastUpdated: null,
    connection: "Not running",
};

const terminal = (status: string) =>
    ["completed", "failed", "infeasible"].includes(status);

function remember(
    scenarioId: string,
    runId: string | null = null,
    runEtag: string | null = null,
) {
    try {
        localStorage.setItem(
            "routing.active",
            JSON.stringify({
                scenario_id: scenarioId,
                run_id: runId,
                run_etag: runEtag,
            }),
        );
    } catch {
        /* Storage may be disabled; server persistence still works in this tab. */
    }
}

export function useWorkspace() {
    const [state, patch] = useReducer(
        (current: Workspace, next: Partial<Workspace>) => ({
            ...current,
            ...next,
        }),
        initial,
    );
    const active = useRef(true);
    const operation = useRef<AbortController | null>(null);
    const generation = useRef(0);
    const current = useRef(state);
    const refreshing = useRef(false);
    const runScenario = useRef<Scenario | null>(null);
    const restoredRun = useRef(false);

    useEffect(() => {
        current.current = state;
    }, [state]);
    useEffect(() => {
        active.current = true;
        const controller = new AbortController();
        const initialize = async () => {
            const { data } = await request<AppConfig>("/config", {
                signal: controller.signal,
            });
            if (controller.signal.aborted) return;
            patch({ config: data });
            let remembered: {
                scenario_id?: unknown;
                run_id?: unknown;
                run_etag?: unknown;
            } | null = null;
            try {
                remembered = JSON.parse(
                    localStorage.getItem("routing.active") ?? "null",
                ) as {
                    scenario_id?: unknown;
                    run_id?: unknown;
                    run_etag?: unknown;
                } | null;
            } catch {
                /* Missing or invalid browser storage does not prevent seed creation. */
            }
            if (!remembered || typeof remembered.scenario_id !== "string")
                return;
            const resource = await request<Scenario>(
                scenarioPath(remembered.scenario_id),
                { signal: controller.signal },
            );
            if (controller.signal.aborted) return;
            patch({
                scenario: resource.data,
                etag: resource.etag,
                lastUpdated: new Date().toISOString(),
            });
            if (typeof remembered.run_id === "string") {
                if (!resource.etag || remembered.run_etag !== resource.etag) {
                    patch({ stale: true });
                    return;
                }
                runScenario.current = resource.data;
                restoredRun.current = true;
                const restored = await request<OptimizationRun>(
                    `${scenarioPath(resource.data.id)}/runs/${encodeURIComponent(remembered.run_id)}`,
                    { signal: controller.signal },
                );
                if (!controller.signal.aborted)
                    patch({ run: restored.data, stale: true });
            }
        };
        void initialize()
            .catch((error: unknown) => {
                if (!controller.signal.aborted) {
                    if (error instanceof ApiError && error.status === 404) {
                        try {
                            localStorage.removeItem("routing.active");
                        } catch {
                            /* Storage is optional. */
                        }
                        patch({
                            error: "The remembered scenario or run has expired. Load a new seed scenario.",
                        });
                    } else patch({ error: errorMessage(error) });
                }
            })
            .finally(() => {
                if (!controller.signal.aborted) patch({ busy: false });
            });
        return () => {
            active.current = false;
            controller.abort();
            operation.current?.abort();
        };
    }, []);

    const transact = useCallback(
        async (action: (signal: AbortSignal) => Promise<void>) => {
            if (operation.current) return;
            const controller = new AbortController();
            operation.current = controller;
            patch({ busy: true, error: null });
            try {
                await action(controller.signal);
            } catch (error) {
                if (!controller.signal.aborted && active.current)
                    patch({ error: errorMessage(error) });
            } finally {
                operation.current = null;
                if (active.current) patch({ busy: false });
            }
        },
        [],
    );

    const seed = () =>
        transact(async (signal) => {
            const created = await request<Scenario>("/scenarios/seed", {
                method: "POST",
                signal,
            });
            const resource = await request<Scenario>(
                scenarioPath(created.data.id),
                { signal },
            );
            generation.current++;
            remember(resource.data.id);
            patch({
                scenario: resource.data,
                etag: resource.etag,
                dirty: false,
                stale: false,
                run: null,
                result: null,
                resultScenario: null,
                previous: null,
                lastUpdated: new Date().toISOString(),
            });
        });

    const edit = useCallback((scenario: Scenario) => {
        // Invalidate in-flight reads immediately, before React commits the editor update.
        generation.current++;
        current.current = {
            ...current.current,
            scenario,
            dirty: true,
            stale: true,
        };
        patch({ scenario, dirty: true, stale: true, error: null });
    }, []);

    const save = () =>
        transact(async (signal) => {
            const { scenario, etag } = current.current;
            if (!scenario || !etag)
                throw new Error(
                    "Reload the server version to obtain its concurrency token.",
                );
            const resource = await request<Scenario>(
                scenarioPath(scenario.id),
                {
                    method: "PUT",
                    headers: { "If-Match": etag },
                    body: JSON.stringify(scenario),
                    signal,
                },
            );
            generation.current++;
            patch({
                scenario: resource.data,
                etag: resource.etag,
                dirty: false,
                lastUpdated: new Date().toISOString(),
            });
        });

    const refresh = useCallback(async (discard = false, rerun = false) => {
        const snapshot = current.current;
        if (
            !snapshot.scenario ||
            operation.current ||
            refreshing.current ||
            (snapshot.run && !terminal(snapshot.run.status)) ||
            (snapshot.dirty && !discard)
        )
            return;
        refreshing.current = true;
        patch({ busy: true });
        const version = generation.current;
        const controller = new AbortController();
        operation.current = controller;
        try {
            const resource = await request<Scenario>(
                scenarioPath(snapshot.scenario.id),
                { signal: controller.signal },
            );
            if (active.current && version === generation.current) {
                const changed =
                    JSON.stringify(snapshot.scenario) !==
                    JSON.stringify(resource.data);
                generation.current++;
                patch({
                    scenario: resource.data,
                    etag: resource.etag,
                    dirty: false,
                    stale: snapshot.stale || changed,
                    error: null,
                    lastUpdated: new Date().toISOString(),
                });
                if (rerun && snapshot.config?.routing_available) {
                    runScenario.current = resource.data;
                    restoredRun.current = false;
                    const run = await request<OptimizationRun>(
                        `${scenarioPath(resource.data.id)}/optimize`,
                        {
                            method: "POST",
                            headers: { "Idempotency-Key": crypto.randomUUID() },
                            signal: controller.signal,
                        },
                    );
                    if (active.current && !controller.signal.aborted) {
                        remember(resource.data.id, run.data.id, resource.etag);
                        patch({
                            run: run.data,
                            previous: snapshot.result,
                            stale: true,
                            connection: "Refreshing optimization snapshot",
                        });
                    }
                }
            }
        } catch (error) {
            if (active.current && !controller.signal.aborted)
                patch({ error: errorMessage(error) });
        } finally {
            operation.current = null;
            refreshing.current = false;
            if (active.current) patch({ busy: false });
        }
    }, []);

    const optimize = () =>
        transact(async (signal) => {
            const snapshot = current.current;
            if (!snapshot.scenario || snapshot.dirty)
                throw new Error("Save your edits before optimizing.");
            runScenario.current = snapshot.scenario;
            restoredRun.current = false;
            const { data } = await request<OptimizationRun>(
                `${scenarioPath(snapshot.scenario.id)}/optimize`,
                {
                    method: "POST",
                    headers: { "Idempotency-Key": crypto.randomUUID() },
                    signal,
                },
            );
            remember(snapshot.scenario.id, data.id, snapshot.etag);
            patch({
                run: data,
                previous: snapshot.result,
                stale: true,
                connection: "Connecting to progress stream",
            });
        });

    const addDisruption = (disruption: Disruption) =>
        transact(async (signal) => {
            const { scenario, etag, dirty } = current.current;
            if (!scenario || !etag || dirty)
                throw new Error("Save your edits before adding a disruption.");
            const resource = await request<Scenario>(
                `${scenarioPath(scenario.id)}/disruptions`,
                {
                    method: "POST",
                    headers: { "If-Match": etag },
                    body: JSON.stringify(disruption),
                    signal,
                },
            );
            generation.current++;
            patch({
                scenario: resource.data,
                etag: resource.etag,
                stale: true,
                lastUpdated: new Date().toISOString(),
            });
        });

    const removeDisruption = (id: string) =>
        transact(async (signal) => {
            const { scenario, etag, dirty } = current.current;
            if (!scenario || !etag || dirty)
                throw new Error("Save edits before removing a disruption.");
            const resource = await request<Scenario>(
                `${scenarioPath(scenario.id)}/disruptions/${encodeURIComponent(id)}`,
                {
                    method: "DELETE",
                    headers: { "If-Match": etag },
                    signal,
                },
            );
            generation.current++;
            patch({
                scenario: resource.data,
                etag: resource.etag,
                stale: true,
                lastUpdated: new Date().toISOString(),
            });
        });

    const runId = state.run?.id;
    const scenarioId = state.run?.scenario_id;
    useEffect(() => {
        if (!runId || !scenarioId) return;
        const controller = new AbortController();
        const streamController = new AbortController();
        let sequence = 0;
        let pending = false;
        let finished = false;
        let lastStamp = -Infinity;
        let lastProgress = 0;
        let queuedRead = false;
        const path = `${scenarioPath(scenarioId)}/runs/${encodeURIComponent(runId)}`;
        const read = async () => {
            if (finished || controller.signal.aborted) return;
            if (pending) {
                queuedRead = true;
                return;
            }
            pending = true;
            try {
                const { data } = await request<OptimizationRun>(path, {
                    signal: controller.signal,
                });
                const stamp = Date.parse(data.updated_at);
                if (
                    controller.signal.aborted ||
                    data.id !== runId ||
                    data.scenario_id !== scenarioId ||
                    stamp < lastStamp ||
                    (stamp === lastStamp && data.progress < lastProgress)
                )
                    return;
                lastStamp = stamp;
                lastProgress = data.progress;
                const done = terminal(data.status);
                patch({
                    run: data,
                    ...(done ? { connection: "Run finished" } : {}),
                });
                if (done) {
                    finished = true;
                    streamController.abort();
                    if (data.status === "completed") {
                        patch({
                            result: data,
                            resultScenario: runScenario.current,
                            stale:
                                restoredRun.current ||
                                current.current.dirty ||
                                JSON.stringify(current.current.scenario) !==
                                    JSON.stringify(runScenario.current),
                            lastUpdated: data.updated_at,
                        });
                    } else
                        patch({
                            error:
                                data.error ||
                                (data.status === "infeasible"
                                    ? "No feasible allocation. Check supply, capacity and closures."
                                    : "Optimization failed."),
                            stale: true,
                        });
                }
            } catch (error) {
                if (!controller.signal.aborted)
                    patch({
                        connection: "Polling interrupted — retrying",
                        error: errorMessage(error),
                    });
            } finally {
                pending = false;
                if (queuedRead && !finished && !controller.signal.aborted) {
                    queuedRead = false;
                    void read();
                }
            }
        };
        void consumeEvents(
            `${path}/events`,
            streamController.signal,
            (message) => {
                if (message.type !== "progress") return;
                try {
                    const event = JSON.parse(message.data) as RunEvent;
                    if (
                        controller.signal.aborted ||
                        event.run_id !== runId ||
                        !Number.isInteger(event.sequence) ||
                        event.sequence < 1 ||
                        event.sequence <= sequence ||
                        finished
                    )
                        return;
                    sequence = event.sequence;
                    patch({ connection: `Live progress · ${event.message}` });
                    // Events carry progress only; always retrieve the complete persisted snapshot.
                    void read();
                } catch {
                    if (!controller.signal.aborted)
                        patch({
                            connection:
                                "Invalid progress event — polling status",
                        });
                }
            },
        )
            .catch(() => {
                // Polling below is the watchdog; do not loop interactive auth or SSE reconnects.
            })
            .finally(() => {
                if (!finished && !controller.signal.aborted) {
                    patch({
                        connection:
                            "Progress stream unavailable — polling status",
                    });
                    void read();
                }
            });
        void read();
        const interval = window.setInterval(() => {
            void read();
        }, 2500);
        return () => {
            controller.abort();
            streamController.abort();
            window.clearInterval(interval);
        };
    }, [runId, scenarioId]);

    return {
        ...state,
        seed,
        edit,
        save,
        refresh,
        optimize,
        addDisruption,
        removeDisruption,
    };
}
