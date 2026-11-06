import {
    act,
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { config, run, scenario } from "./test-fixtures";
import type { Disruption, Scenario } from "./types";

vi.mock("azure-maps-control", () => ({}));

class MockStream {
    static instances: MockStream[] = [];
    controller!: ReadableStreamDefaultController<Uint8Array>;
    close = vi.fn();
    response: Response;
    constructor() {
        this.response = new Response(
            new ReadableStream<Uint8Array>({
                start: (controller) => {
                    this.controller = controller;
                },
                cancel: this.close,
            }),
            { headers: { "Content-Type": "text/event-stream" } },
        );
        MockStream.instances.push(this);
    }
    emit(sequence: number, runId = run.id) {
        if (this.close.mock.calls.length) return;
        this.controller.enqueue(
            new TextEncoder().encode(
                `event: progress\ndata: ${JSON.stringify({
                    sequence,
                    run_id: runId,
                    status: "completed",
                    progress: 1,
                    stage: "completed",
                    message: "Done",
                })}\n\n`,
            ),
        );
    }
}

function setupApi({ stale = false, running = false } = {}) {
    let saved = structuredClone(scenario);
    let completed = !running;
    const fetch = vi.fn(async (url: string, options: RequestInit = {}) => {
        const response = (data: unknown, status = 200) =>
            new Response(JSON.stringify(data), {
                status,
                headers: { "Content-Type": "application/json", ETag: '"v1"' },
            });
        if (url === "/api/config") return response(config);
        if (url.endsWith("/events")) return new MockStream().response;
        if (url.endsWith("/locations:geocode"))
            return response([
                {
                    address: "Houston, TX, USA",
                    latitude: 29.76,
                    longitude: -95.37,
                },
                {
                    address: "Houston Heights, TX",
                    latitude: 29.8,
                    longitude: -95.4,
                },
            ]);
        if (url.endsWith("/disruptions")) {
            saved.disruptions.push(
                JSON.parse(options.body as string) as Disruption,
            );
            return response(saved, 201);
        }
        if (url.endsWith("/optimize"))
            return response(
                {
                    ...run,
                    status: "queued",
                    stage: "queued",
                    progress: 0,
                    routes: [],
                    allocations: [],
                },
                202,
            );
        if (url.includes("/runs/"))
            return response(
                completed
                    ? run
                    : {
                          ...run,
                          status: "running",
                          stage: "routes",
                          progress: 0.5,
                          routes: [],
                          allocations: [],
                      },
            );
        if (options.method === "PUT") {
            if (stale) return response({ detail: "Out of date" }, 412);
            saved = JSON.parse(options.body as string) as Scenario;
        }
        return response(saved);
    });
    vi.stubGlobal("fetch", fetch);
    return {
        fetch,
        complete: () => {
            completed = true;
        },
    };
}

async function seed() {
    const button = await screen.findByRole("button", {
        name: /Load Houston sample/,
    });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    await screen.findByRole("textbox", { name: "Scenario name" });
}

beforeEach(() => {
    MockStream.instances = [];
});

describe("network planning workspace", () => {
    it("edits and persists full scenarios with ETags, optimizes, selects alternatives, and applies a closure", async () => {
        const { fetch } = setupApi();
        render(<App />);
        expect(await screen.findByText(/SIMULATION MODE/)).toBeInTheDocument();
        await seed();
        expect(
            screen.getByRole("group", { name: /Coordinate schematic/ }),
        ).toBeInTheDocument();
        fireEvent.change(screen.getAllByLabelText("Supply (units)")[0], {
            target: { value: "75" },
        });
        expect(
            screen.getByRole("button", { name: "Optimize network" }),
        ).toBeDisabled();
        fireEvent.click(screen.getByRole("button", { name: "Save scenario" }));
        await waitFor(() =>
            expect(
                screen.getByRole("button", { name: "Optimize network" }),
            ).toBeEnabled(),
        );
        expect(fetch).toHaveBeenCalledWith(
            "/api/scenarios/scenario-1",
            expect.objectContaining({
                method: "PUT",
                headers: expect.objectContaining({ "if-match": '"v1"' }),
                body: expect.stringContaining('"quantity":75'),
            }),
        );
        fireEvent.click(
            screen.getByRole("button", { name: "Optimize network" }),
        );
        await screen.findByRole("table");
        expect(
            within(screen.getByRole("table")).getByText("$10,000.00"),
        ).toBeInTheDocument();
        fireEvent.click(
            screen.getByRole("button", { name: /2 Houston supply/ }),
        );
        expect(
            screen.getByRole("button", { name: /2 Houston supply/ }),
        ).toHaveAttribute("aria-pressed", "true");
        expect(
            screen.getByText(/Hypothetical full supplier supply/),
        ).toBeInTheDocument();
        fireEvent.click(screen.getByRole("tab", { name: "Disruptions" }));
        fireEvent.change(screen.getByLabelText("Route to close"), {
            target: { value: "route-1" },
        });
        fireEvent.click(
            screen.getByRole("button", { name: "Apply disruption" }),
        );
        await screen.findByRole("button", {
            name: "Remove disruption Closure: Houston supply → Baytown factory",
        });
        expect(fetch).toHaveBeenCalledWith(
            "/api/scenarios/scenario-1/disruptions",
            expect.objectContaining({
                method: "POST",
                body: expect.stringContaining('"route_id":"route-1"'),
            }),
        );
        expect(screen.getByText(/Results may be stale/)).toBeInTheDocument();
        fireEvent.click(
            screen.getByRole("button", { name: "Optimize network" }),
        );
        await waitFor(() =>
            expect(
                fetch.mock.calls.filter(([url]) => url.endsWith("/optimize")),
            ).toHaveLength(2),
        );
    });

    it("preserves unsaved input on 412 and requires explicit reload", async () => {
        setupApi({ stale: true });
        render(<App />);
        await seed();
        fireEvent.change(screen.getByLabelText("Scenario name"), {
            target: { value: "My local edit" },
        });
        fireEvent.click(screen.getByRole("button", { name: "Save scenario" }));
        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Your edits are preserved",
        );
        expect(screen.getByLabelText("Scenario name")).toHaveValue(
            "My local edit",
        );
        expect(
            screen.getByText(/Refresh paused to protect unsaved edits/),
        ).toBeInTheDocument();
        fireEvent.click(
            screen.getByRole("button", { name: "Discard edits & reload" }),
        );
        await waitFor(() =>
            expect(screen.getByLabelText("Scenario name")).toHaveValue(
                scenario.name,
            ),
        );
    });

    it("retrieves persisted full runs after SSE events, rejects old events, and closes resources", async () => {
        const api = setupApi({ running: true });
        const view = render(<App />);
        await seed();
        fireEvent.click(
            screen.getByRole("button", { name: "Optimize network" }),
        );
        await screen.findByText(/RUNNING · routes/);
        const source = MockStream.instances[0];
        await act(async () => {
            source.emit(2);
        });
        const reads = api.fetch.mock.calls.length;
        await act(async () => {
            source.emit(1);
            source.emit(9, "unrelated-run");
        });
        expect(api.fetch.mock.calls.length).toBe(reads);
        api.complete();
        await act(async () => {
            source.emit(3);
        });
        await screen.findByRole("table");
        expect(source.close).toHaveBeenCalled();
        view.unmount();
        expect(source.close).toHaveBeenCalled();
        const afterUnmount = api.fetch.mock.calls.length;
        await act(async () => {
            source.emit(4);
        });
        expect(api.fetch.mock.calls.length).toBe(afterUnmount);
    });

    it("falls back to polling on a broken progress stream", async () => {
        const api = setupApi({ running: true });
        render(<App />);
        await seed();
        fireEvent.click(
            screen.getByRole("button", { name: "Optimize network" }),
        );
        await screen.findByText(/RUNNING · routes/);
        api.complete();
        await act(async () => {
            MockStream.instances[0].controller.error(
                new Error("Connection lost"),
            );
        });
        await screen.findByRole("table");
        expect(screen.getByText(/Run finished/)).toBeInTheDocument();
    });

    it("lets users choose geocode results and validates disruption targets before sending", async () => {
        const { fetch } = setupApi();
        render(<App />);
        await seed();
        fireEvent.click(
            screen.getAllByRole("button", { name: "Find address" })[0],
        );
        const matches = await screen.findByRole("group", {
            name: "Choose an address match",
        });
        fireEvent.click(
            within(matches).getByRole("button", { name: /Houston, TX, USA/ }),
        );
        expect(screen.getAllByLabelText("Latitude")[0]).toHaveValue(29.76);
        fireEvent.click(screen.getByRole("button", { name: "Save scenario" }));
        fireEvent.click(screen.getByRole("tab", { name: "Disruptions" }));
        await waitFor(() =>
            expect(
                screen.getByRole("button", { name: "Apply disruption" }),
            ).toBeEnabled(),
        );
        fireEvent.click(
            screen.getByRole("button", { name: "Apply disruption" }),
        );
        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Choose a valid target",
        );
        expect(
            fetch.mock.calls.some(([url]) => url.endsWith("/disruptions")),
        ).toBe(false);
    });

    it("shows configuration failures instead of claiming live availability", async () => {
        vi.stubGlobal(
            "fetch",
            vi
                .fn()
                .mockResolvedValue(
                    new Response("unavailable", { status: 503 }),
                ),
        );
        render(<App />);
        expect(await screen.findByRole("alert")).toHaveTextContent("503");
        expect(
            screen.getByRole("button", { name: /Load Houston sample/ }),
        ).toBeDisabled();
    });

    it("refreshes saved inputs on schedule but pauses for unsaved edits", async () => {
        const { fetch } = setupApi();
        render(<App />);
        await seed();
        vi.useFakeTimers();
        try {
            vi.spyOn(document, "visibilityState", "get").mockReturnValue(
                "visible",
            );
            fireEvent.change(screen.getByLabelText("Refresh interval"), {
                target: { value: "120" },
            });
            await act(async () => {
                await vi.advanceTimersByTimeAsync(120000);
            });
            expect(
                fetch.mock.calls.filter(([url]) => url.endsWith("/optimize")),
            ).toHaveLength(1);
            fireEvent.change(screen.getByLabelText("Scenario name"), {
                target: { value: "Local work" },
            });
            await act(async () => {
                await vi.advanceTimersByTimeAsync(120000);
            });
            expect(
                fetch.mock.calls.filter(([url]) => url.endsWith("/optimize")),
            ).toHaveLength(1);
            expect(screen.getByLabelText("Scenario name")).toHaveValue(
                "Local work",
            );
            expect(
                screen.getByText(/Refresh paused to protect unsaved edits/),
            ).toBeInTheDocument();
        } finally {
            vi.useRealTimers();
        }
    });

    it("restores remembered scenario and run identifiers without enumerating other scenarios", async () => {
        const { fetch } = setupApi();
        localStorage.setItem(
            "routing.active",
            JSON.stringify({
                scenario_id: scenario.id,
                run_id: run.id,
                run_etag: '"v1"',
            }),
        );
        render(<App />);
        await screen.findByRole("table");
        expect(screen.getByLabelText("Scenario name")).toHaveValue(
            scenario.name,
        );
        expect(screen.getByText(/Results may be stale/)).toBeInTheDocument();
        expect(fetch.mock.calls.some(([url]) => url === "/api/scenarios")).toBe(
            false,
        );
    });

    it("reports a failed run instead of displaying successful empty results", async () => {
        const { fetch } = setupApi();
        const original = fetch.getMockImplementation()!;
        fetch.mockImplementation(async (url, options) =>
            url.includes("/runs/") && !url.endsWith("/events")
                ? new Response(
                      JSON.stringify({
                          ...run,
                          status: "failed",
                          error: "Azure routing unavailable",
                          routes: [],
                          allocations: [],
                      }),
                  )
                : original(url, options),
        );
        render(<App />);
        await seed();
        fireEvent.click(
            screen.getByRole("button", { name: "Optimize network" }),
        );
        expect(await screen.findByRole("alert")).toHaveTextContent(
            "Azure routing unavailable",
        );
        expect(screen.queryByRole("table")).not.toBeInTheDocument();
    });

    it("does not restore route costs under a newer scenario's different assumptions", async () => {
        const { fetch } = setupApi();
        localStorage.setItem(
            "routing.active",
            JSON.stringify({
                scenario_id: scenario.id,
                run_id: run.id,
                run_etag: '"older-version"',
            }),
        );
        render(<App />);
        await screen.findByLabelText("Scenario name");
        expect(screen.queryByRole("table")).not.toBeInTheDocument();
        expect(fetch.mock.calls.some(([url]) => url.includes("/runs/"))).toBe(
            false,
        );
    });

    it("ignores an older persisted snapshot even when its SSE sequence is newer", async () => {
        const { fetch } = setupApi({ running: true });
        const original = fetch.getMockImplementation()!;
        let newer = true;
        fetch.mockImplementation(async (url, options) =>
            url.includes("/runs/") && !url.endsWith("/events")
                ? new Response(
                      JSON.stringify({
                          ...run,
                          status: "running",
                          updated_at: newer
                              ? "2026-11-06T14:02:00Z"
                              : "2026-11-06T14:01:00Z",
                          stage: newer ? "allocation" : "routes",
                          progress: newer ? 0.75 : 0.25,
                          routes: [],
                          allocations: [],
                      }),
                  )
                : original(url, options),
        );
        render(<App />);
        await seed();
        fireEvent.click(
            screen.getByRole("button", { name: "Optimize network" }),
        );
        await screen.findByText(/RUNNING · allocation/);
        newer = false;
        await act(async () => {
            MockStream.instances[0].emit(2);
        });
        expect(screen.getByText(/RUNNING · allocation/)).toBeInTheDocument();
        expect(screen.queryByText(/RUNNING · routes/)).not.toBeInTheDocument();
    });
});
