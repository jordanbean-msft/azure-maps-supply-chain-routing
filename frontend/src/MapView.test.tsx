import {
    act,
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import MapView from "./MapView";
import { run, scenario } from "./test-fixtures";
import type { Disruption } from "./types";

const sdk = vi.hoisted(() => ({
    events: [] as {
        name: string;
        target: unknown;
        handler: (...args: unknown[]) => void;
    }[],
    options: null as null | {
        center: number[];
        style: string;
        authOptions: {
            clientId: string;
            getToken: (
                resolve: (token: string) => void,
                reject: (error: unknown) => void,
            ) => void;
        };
    },
    markers: [] as {
        getOptions: () => { position: number[]; draggable: boolean };
        node: HTMLButtonElement;
    }[],
    sources: [] as {
        shapes: {
            properties: {
                route_id: string;
                label: string;
                shipment_label: string;
            };
        }[];
    }[],
    layers: [] as unknown[],
    popup: { content: null as HTMLElement | null, position: [] as number[] },
    construct: vi.fn(),
    dispose: vi.fn(),
    setCamera: vi.fn(),
    setTraffic: vi.fn(),
    controls: vi.fn(),
    popupOpen: vi.fn(),
    popupRemove: vi.fn(),
    removeEvent: vi.fn(),
    removeLayer: vi.fn(),
    removeSource: vi.fn(),
    removeMarker: vi.fn(),
    resized: vi.fn(),
}));

vi.mock("azure-maps-control", () => ({
    AuthenticationType: { anonymous: "anonymous" },
    ControlPosition: { TopRight: "top-right" },
    Map: class {
        element: HTMLElement;
        constructor(element: HTMLElement, options: typeof sdk.options) {
            sdk.options = options;
            sdk.construct(options);
            this.element = element;
        }
        controls = { add: sdk.controls };
        sources = {
            add: (sources: typeof sdk.sources) => sdk.sources.push(...sources),
            remove: sdk.removeSource,
        };
        layers = {
            add: (layers: unknown[]) => sdk.layers.push(...layers),
            remove: sdk.removeLayer,
        };
        markers = {
            add: (marker: (typeof sdk.markers)[number]) => {
                sdk.markers.push(marker);
                this.element.append(marker.node);
            },
            remove: (marker: (typeof sdk.markers)[number]) => {
                sdk.removeMarker(marker);
                marker.node.remove();
            },
        };
        events = {
            add: (name: string, ...args: unknown[]) => {
                sdk.events.push({
                    name,
                    target: args.length > 1 ? args[0] : null,
                    handler: args.at(-1) as (...args: unknown[]) => void,
                });
            },
            remove: sdk.removeEvent,
        };
        dispose = sdk.dispose;
        setCamera = sdk.setCamera;
        setTraffic = sdk.setTraffic;
        resize = sdk.resized;
    },
    HtmlMarker: class {
        node: HTMLButtonElement;
        options = { position: [] as number[], draggable: false };
        constructor(options: { htmlContent: HTMLButtonElement }) {
            this.node = options.htmlContent;
        }
        setOptions = (options: typeof this.options) => {
            this.options = options;
        };
        getOptions = () => this.options;
    },
    Popup: class {
        setOptions = (options: typeof sdk.popup) => {
            sdk.popup = options;
        };
        open = sdk.popupOpen;
        close = vi.fn();
        remove = sdk.popupRemove;
    },
    Shape: class {},
    source: {
        DataSource: class {
            shapes = [];
            setShapes = (shapes: []) => {
                this.shapes = shapes;
            };
        },
    },
    layer: {
        LineLayer: class {
            constructor(
                public source: unknown,
                _id: unknown,
                public options: Record<string, unknown>,
            ) {}
        },
        SymbolLayer: class {
            kind = "label";
            constructor(
                public source: unknown,
                _id: unknown,
                public options: Record<string, unknown>,
            ) {}
        },
    },
    data: {
        Feature: class {
            geometry: unknown;
            properties: unknown;
            constructor(geometry: unknown, properties: unknown) {
                this.geometry = geometry;
                this.properties = properties;
            }
        },
        LineString: class {},
        BoundingBox: { fromPositions: (positions: number[][]) => positions },
    },
    control: {
        ZoomControl: class {},
        CompassControl: class {},
        StyleControl: class {},
    },
}));

const props = {
    mapsAvailable: false,
    locations: scenario.locations,
    routes: run.routes,
    allocations: run.allocations,
    selected: run.routes[0].id,
    disabled: false,
    onMove: vi.fn(),
    onSelect: vi.fn(),
    onSelectLocation: vi.fn(),
};

const closure: Disruption = {
    id: "closure",
    kind: "road_closure",
    name: "Simulated lane closure",
    route_id: run.routes[0].id,
    location_id: null,
    delay_minutes: 0,
    severity: 1,
    fuel_price_per_liter: null,
    enabled: true,
};
const delay: Disruption = {
    ...closure,
    id: "delay",
    kind: "facility_delay",
    name: "Loading delay",
    route_id: null,
    location_id: scenario.locations[0].id,
    delay_minutes: 45,
};
const weather: Disruption = {
    ...closure,
    id: "weather",
    kind: "weather",
    name: "Heavy rain",
    route_id: null,
};

beforeEach(() => {
    vi.clearAllMocks();
    sdk.events = [];
    sdk.sources = [];
    sdk.layers = [];
    sdk.markers = [];
    sdk.options = null;
    sdk.popup = { content: null, position: [] };
    vi.stubGlobal(
        "fetch",
        vi.fn().mockImplementation(() =>
            Promise.resolve(
                new Response(
                    JSON.stringify({
                        token: "short-lived-token",
                        client_id: "maps-client",
                        expires_on: "2099-01-01T00:00:00Z",
                    }),
                ),
            ),
        ),
    );
});

afterEach(() => {
    vi.useRealTimers();
});

async function ready(): Promise<void> {
    await waitFor(() => expect(sdk.options).not.toBeNull());
    act(() => sdk.events.find((event) => event.name === "ready")?.handler());
}

function emit(name: string, target: unknown = null, value?: unknown): void {
    act(() =>
        sdk.events
            .find((event) => event.name === name && event.target === target)
            ?.handler(value),
    );
}

it("shows every recommended shipment by default and reveals unused options only on request or inspection", () => {
    const view = render(<MapView {...props} selected={null} />);
    const schematic = screen.getByRole("group", {
        name: /Coordinate schematic/,
    });
    const routes = () =>
        within(schematic).getAllByRole("button", { name: /^Select route / });
    expect(routes()).toHaveLength(1);
    expect(routes()[0]).toHaveAccessibleDescription(
        expect.stringContaining("Recommended shipment · 50 units"),
    );
    expect(within(schematic).getByText("50 units")).toBeVisible();
    expect(screen.queryByText(/^INSPECTED/)).not.toBeInTheDocument();
    const toggle = screen.getByRole("checkbox", {
        name: "Show unused alternatives (1)",
    });
    expect(toggle).not.toBeChecked();
    fireEvent.click(toggle);
    expect(routes()).toHaveLength(2);
    expect(
        within(schematic).getByRole("button", { name: "Select route route-2" }),
    ).toHaveAccessibleDescription(
        expect.stringContaining("Unused alternative · no shipments"),
    );
    fireEvent.click(toggle);
    expect(routes()).toHaveLength(1);
    view.rerender(<MapView {...props} selected="route-2" />);
    expect(routes()).toHaveLength(2);
    expect(screen.getByText(/^INSPECTED/)).toHaveTextContent(
        "Unused alternative · no shipments",
    );
    view.rerender(<MapView {...props} selected={null} />);
    expect(routes()).toHaveLength(1);
});

it("draws all positive allocations in the plan layer, keeps alternatives and labels separate, and never resets the camera when toggling", async () => {
    const allocations = [
        { ...run.allocations[0], quantity: 30 },
        { ...run.allocations[0], route_id: "route-2", quantity: 20 },
    ];
    const unused = { ...run.routes[0], id: "unused" };
    const zeroQuantity = {
        ...run.allocations[0],
        route_id: "unused",
        quantity: 0,
    };
    const view = render(
        <MapView
            {...props}
            mapsAvailable
            routes={[...run.routes, unused]}
            allocations={[...allocations, zeroQuantity]}
            selected={null}
        />,
    );
    await ready();
    expect(sdk.options?.style).toBe("grayscale_light");
    const plan = sdk.sources[4];
    expect(plan.shapes.map((shape) => shape.properties.route_id)).toEqual([
        "route-1",
        "route-2",
    ]);
    expect(plan.shapes.map((shape) => shape.properties.shipment_label)).toEqual(
        ["30 units", "20 units"],
    );
    expect(sdk.sources[0].shapes).toEqual([]);
    expect(sdk.sources[1].shapes).toEqual([]);
    expect(
        sdk.layers.filter(
            (layer) => (layer as { kind?: string }).kind === "label",
        ),
    ).toEqual([
        expect.objectContaining({ source: sdk.sources[4] }),
        expect.objectContaining({ source: sdk.sources[1] }),
    ]);
    expect(sdk.layers).toEqual(
        expect.arrayContaining([
            expect.objectContaining({
                source: plan,
                options: { strokeColor: "#ffffff", strokeWidth: 10 },
            }),
            expect.objectContaining({
                source: plan,
                options: { strokeColor: "#0078d4", strokeWidth: 6 },
            }),
            expect.objectContaining({
                source: sdk.sources[0],
                options: {
                    strokeColor: "#5c6873",
                    strokeWidth: 2,
                    strokeDashArray: [3, 3],
                },
            }),
        ]),
    );
    fireEvent.click(
        screen.getByRole("checkbox", { name: /Show unused alternatives/ }),
    );
    expect(
        sdk.sources[0].shapes.map((shape) => shape.properties.route_id),
    ).toEqual(["unused"]);
    expect(plan.shapes).toHaveLength(2);
    view.rerender(
        <MapView
            {...props}
            mapsAvailable
            routes={[...run.routes, unused]}
            allocations={allocations}
            selected="unused"
            target={{ kind: "network", id: null }}
        />,
    );
    expect(sdk.sources[1].shapes[0].properties.route_id).toBe("unused");
    expect(sdk.sources[2].shapes).toEqual([]);
    expect(sdk.setCamera).toHaveBeenCalledTimes(1);
    expect(sdk.construct).toHaveBeenCalledTimes(1);
});

it("keeps a targeted unused route visible without pretending it carries a shipment", async () => {
    render(
        <MapView
            {...props}
            mapsAvailable
            selected={null}
            target={{ kind: "route", id: "route-2" }}
        />,
    );
    await ready();
    expect(sdk.sources[0].shapes[0].properties.route_id).toBe("route-2");
    expect(sdk.sources[2].shapes[0].properties.route_id).toBe("route-2");
    expect(
        sdk.sources[4].shapes.map((shape) => shape.properties.route_id),
    ).toEqual(["route-1"]);
    expect(sdk.sources[1].shapes).toEqual([]);
});

it("offers named lanes, source estimates and mouse/keyboard facility and route inspection in the schematic", () => {
    render(<MapView {...props} />);
    fireEvent.click(
        screen.getByRole("checkbox", { name: /Show unused alternatives/ }),
    );
    const schematic = screen.getByRole("group", {
        name: /Coordinate schematic/,
    });
    const routes = run.routes.map((route) =>
        within(schematic).getByRole("button", {
            name: `Select route ${route.id}`,
        }),
    );
    expect(routes[0]).toHaveAccessibleDescription(
        expect.stringContaining(scenario.locations[0].name),
    );
    expect(routes[0]).toHaveAccessibleDescription(
        expect.stringContaining("450.0 km"),
    );
    fireEvent.click(routes[0]);
    fireEvent.keyDown(routes[1], { key: " " });
    expect(props.onSelect.mock.calls).toEqual([
        [run.routes[0].id],
        [run.routes[1].id],
    ]);
    const facility = within(schematic).getByRole("button", {
        name: `Select facility ${scenario.locations[0].name}`,
    });
    fireEvent.keyDown(facility, { key: "Enter" });
    fireEvent.click(
        within(schematic).getByRole("button", {
            name: `Select facility ${scenario.locations[1].name}`,
        }),
    );
    expect(props.onSelectLocation.mock.calls).toEqual([
        [scenario.locations[0].id],
        [scenario.locations[1].id],
    ]);
    expect(
        screen.getByText(/INSPECTED · .*Simulated estimate/),
    ).toBeInTheDocument();
    expect(screen.getByText(/not live road closures/)).toBeInTheDocument();
});

it("distinguishes preview, inspection and enabled closures/delays without applying disabled disruptions", () => {
    const view = render(
        <MapView
            {...props}
            target={{ kind: "route", id: run.routes[1].id }}
            selectedLocation={scenario.locations[0].id}
            disruptions={[closure, delay]}
        />,
    );
    const schematic = screen.getByRole("group", {
        name: /Coordinate schematic/,
    });
    const routes = run.routes.map((route) =>
        within(schematic).getByRole("button", {
            name: `Select route ${route.id}`,
        }),
    );
    expect(routes[0]).toHaveAccessibleDescription(
        expect.stringContaining("ENABLED · CLOSED"),
    );
    expect(routes[1]).toHaveAccessibleDescription(
        expect.stringContaining("TARGET PREVIEW"),
    );
    expect(
        within(schematic).getByRole("button", {
            name: `Select facility ${scenario.locations[0].name}`,
        }),
    ).toHaveAttribute("aria-pressed", "true");
    view.rerender(
        <MapView
            {...props}
            target={{ kind: "facility", id: scenario.locations[0].id }}
            disruptions={[
                { ...closure, enabled: false },
                { ...delay, enabled: false },
            ]}
        />,
    );
    expect(routes[0]).not.toHaveAccessibleDescription(
        expect.stringContaining("ENABLED · CLOSED"),
    );
    expect(within(schematic).queryByText(/DELAYED 45/)).not.toBeInTheDocument();
    const supplier = within(schematic).getByRole("button", {
        name: `Select facility ${scenario.locations[0].name}`,
    });
    expect(within(supplier).getByText("TARGET PREVIEW")).toBeInTheDocument();
});

it("keeps global previews textual rather than recoloring all routes and handles a network without routes", () => {
    const view = render(
        <MapView
            {...props}
            target={{ kind: "network", id: null }}
            disruptions={[weather]}
        />,
    );
    const schematic = screen.getByRole("group", {
        name: /Coordinate schematic/,
    });
    const lanes = within(schematic).getAllByRole("button", {
        name: /^Select route /,
    });
    lanes.forEach((lane) =>
        expect(lane).not.toHaveAccessibleDescription(
            expect.stringContaining("TARGET PREVIEW"),
        ),
    );
    expect(
        screen.getByText(
            /ENABLED · ENTIRE NETWORK · Heavy rain · all 2 routes affected/,
        ),
    ).toBeInTheDocument();
    view.rerender(
        <MapView
            {...props}
            routes={[]}
            target={{ kind: "network", id: null }}
            disruptions={[weather]}
        />,
    );
    expect(
        screen.getByText(/No routes yet. Save and calculate a shipment plan/),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
        "Entire network · all 0 routes affected · no routes yet",
    );
});

it("shows the Houston default region before facilities or routes exist", async () => {
    const view = render(<MapView {...props} locations={[]} routes={[]} />);
    expect(
        screen.getByText("Houston region · 29.7604° N, 95.3698° W"),
    ).toBeInTheDocument();
    expect(
        screen.getByText("Add facilities to display your network"),
    ).toBeInTheDocument();
    view.rerender(
        <MapView {...props} mapsAvailable locations={[]} routes={[]} />,
    );
    await ready();
    expect(sdk.options?.center).toEqual([-95.3698, 29.7604]);
    expect(sdk.setCamera).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Fit network" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Fit selected" })).toBeDisabled();
});

it("keeps the SDK viewport, layers and facility markers stable across inspection, target and locked-state changes", async () => {
    const view = render(<MapView {...props} mapsAvailable />);
    await ready();
    const originalLayers = [...sdk.layers];
    const originalMarkers = [...sdk.markers];
    const originalSources = [...sdk.sources];
    expect(sdk.setCamera).toHaveBeenCalledTimes(1);
    const onSelect = vi.fn();
    const onSelectLocation = vi.fn();
    view.rerender(
        <MapView
            {...props}
            mapsAvailable
            locations={scenario.locations.map((location) => ({ ...location }))}
            routes={run.routes.map((route) => ({
                ...route,
                geometry: [...route.geometry],
            }))}
            selected={run.routes[1].id}
            selectedLocation={scenario.locations[0].id}
            target={{ kind: "route", id: run.routes[0].id }}
            disruptions={[closure, delay]}
            disabled
            onSelect={onSelect}
            onSelectLocation={onSelectLocation}
        />,
    );
    expect(sdk.construct).toHaveBeenCalledTimes(1);
    expect(sdk.layers).toEqual(originalLayers);
    expect(sdk.markers).toEqual(originalMarkers);
    expect(sdk.sources).toEqual(originalSources);
    expect(sdk.setCamera).toHaveBeenCalledTimes(1);
    expect(sdk.removeMarker).not.toHaveBeenCalled();
    expect(sdk.removeLayer).not.toHaveBeenCalled();
    expect(sdk.sources[1].shapes[0].properties.route_id).toBe(run.routes[1].id);
    expect(sdk.sources[2].shapes[0].properties.route_id).toBe(run.routes[0].id);
    expect(sdk.sources[3].shapes[0].properties.route_id).toBe(run.routes[0].id);
    expect(sdk.sources[4].shapes[0].properties.label).toContain(
        "Recommended shipment · 50 units",
    );
    const marker = sdk.markers[0];
    expect(marker.getOptions().draggable).toBe(false);
    expect(marker.node).toHaveTextContent("ENABLED · DELAYED 45 min");
    expect(marker.node).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(marker.node);
    expect(onSelectLocation).toHaveBeenCalledWith(scenario.locations[0].id);
    emit("click", sdk.layers[0], {
        shapes: [{ properties: { route_id: run.routes[1].id } }],
        position: [-95, 29],
    });
    expect(onSelect).toHaveBeenCalledWith(run.routes[1].id);
    emit("dragend", marker);
    expect(props.onMove).not.toHaveBeenCalled();
});

it("fits network and inspected geometry only on explicit actions or topology edits", async () => {
    const view = render(<MapView {...props} mapsAvailable />);
    await ready();
    sdk.setCamera.mockClear();
    fireEvent.click(screen.getByRole("button", { name: "Fit selected" }));
    expect(sdk.setCamera).toHaveBeenLastCalledWith(
        expect.objectContaining({ bounds: run.routes[0].geometry }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Fit network" }));
    expect(sdk.setCamera).toHaveBeenLastCalledWith(
        expect.objectContaining({
            bounds: [
                ...scenario.locations.map((item) => [
                    item.longitude,
                    item.latitude,
                ]),
                ...run.routes.flatMap((route) => route.geometry),
            ],
        }),
    );
    view.rerender(
        <MapView
            {...props}
            mapsAvailable
            selectedLocation={scenario.locations[1].id}
        />,
    );
    expect(sdk.setCamera).toHaveBeenCalledTimes(2);
    fireEvent.click(screen.getByRole("button", { name: "Fit selected" }));
    expect(sdk.setCamera).toHaveBeenLastCalledWith(
        expect.objectContaining({
            center: [
                scenario.locations[1].longitude,
                scenario.locations[1].latitude,
            ],
        }),
    );
    const moved = { ...scenario.locations[0], longitude: -95.8 };
    view.rerender(
        <MapView
            {...props}
            mapsAvailable
            locations={[moved, scenario.locations[1]]}
        />,
    );
    expect(sdk.setCamera).toHaveBeenCalledTimes(4);
    expect(sdk.markers[0].getOptions().position).toEqual([
        moved.longitude,
        moved.latitude,
    ]);
    expect(sdk.markers).toHaveLength(2);
});

it("uses Houston defaults, token auth, real traffic and road/satellite controls and disposes resources", async () => {
    const observe = vi.fn(),
        disconnect = vi.fn();
    let resize: (() => void) | undefined;
    vi.stubGlobal(
        "ResizeObserver",
        class {
            constructor(callback: () => void) {
                resize = callback;
            }
            observe = observe;
            disconnect = disconnect;
        },
    );
    const view = render(<MapView {...props} mapsAvailable />);
    await ready();
    expect(sdk.options?.center).toEqual([-95.3698, 29.7604]);
    expect(sdk.options?.authOptions.clientId).toBe("maps-client");
    const resolve = vi.fn(),
        reject = vi.fn();
    await act(async () => sdk.options?.authOptions.getToken(resolve, reject));
    expect(resolve).toHaveBeenCalledWith("short-lived-token");
    expect(reject).not.toHaveBeenCalled();
    expect(sdk.controls.mock.calls[0][0]).toHaveLength(3);
    fireEvent.click(
        screen.getByRole("checkbox", { name: "Live traffic overlay" }),
    );
    expect(sdk.setTraffic).toHaveBeenLastCalledWith({
        flow: "relative",
        incidents: true,
    });
    fireEvent.click(
        screen.getByRole("checkbox", { name: "Live traffic overlay" }),
    );
    expect(sdk.setTraffic).toHaveBeenLastCalledWith({
        flow: "none",
        incidents: false,
    });
    resize?.();
    expect(sdk.resized).toHaveBeenCalled();
    const marker = sdk.markers[0];
    marker.getOptions().position = [-95.1, 29.9];
    emit("dragend", marker);
    expect(props.onMove).toHaveBeenCalledWith({
        ...scenario.locations[0],
        longitude: -95.1,
        latitude: 29.9,
    });
    view.unmount();
    expect(sdk.dispose).toHaveBeenCalledTimes(1);
    expect(disconnect).toHaveBeenCalledTimes(1);
    expect(sdk.popupRemove).toHaveBeenCalledTimes(1);
    expect(sdk.removeLayer).toHaveBeenCalledWith(sdk.layers);
    expect(sdk.removeSource).toHaveBeenCalledTimes(5);
    expect(sdk.removeMarker).toHaveBeenCalledTimes(2);
    fireEvent.click(marker.node);
    expect(props.onSelectLocation).not.toHaveBeenCalled();
    const signal = vi.mocked(fetch).mock.calls[0][1]?.signal as AbortSignal;
    expect(signal.aborted).toBe(true);
});

it("uses safe DOM popup content for user-supplied names and includes estimate labels", async () => {
    const unsafe = {
        ...scenario.locations[0],
        name: '<img src="x" onerror="alert(1)">',
    };
    render(
        <MapView
            {...props}
            mapsAvailable
            locations={[unsafe, scenario.locations[1]]}
        />,
    );
    await ready();
    fireEvent.click(sdk.markers[0].node);
    expect(sdk.popupOpen).toHaveBeenCalled();
    expect(sdk.popup.content?.querySelector("img")).toBeNull();
    expect(sdk.popup.content?.textContent).toContain(unsafe.name);
    emit("click", sdk.layers[0], {
        shapes: [{ properties: { route_id: run.routes[0].id } }],
        position: [-95, 29],
    });
    expect(sdk.popup.content?.textContent).toContain("Simulated estimate");
    expect(sdk.popup.content?.textContent).toContain("450.0 km · ETA 310 min");
    expect(sdk.popup.content?.querySelector("img")).toBeNull();
});

it("includes weather and simulated delays in map ETA without counting traffic twice", () => {
    render(
        <MapView
            {...props}
            routes={[{ ...run.routes[0], simulated_delay_minutes: 30 }]}
        />,
    );
    expect(screen.getByText(/^INSPECTED ·/)).toHaveTextContent("ETA 340 min");
});

it("updates a facility preview and removes deleted markers without resetting inspection viewport", async () => {
    const view = render(<MapView {...props} mapsAvailable />);
    await ready();
    view.rerender(
        <MapView
            {...props}
            mapsAvailable
            target={{ kind: "facility", id: scenario.locations[0].id }}
        />,
    );
    expect(sdk.markers[0].node).toHaveTextContent("TARGET PREVIEW");
    expect(sdk.setCamera).toHaveBeenCalledTimes(1);
    const removed = sdk.markers[1];
    view.rerender(
        <MapView
            {...props}
            mapsAvailable
            locations={[scenario.locations[0]]}
        />,
    );
    expect(sdk.removeMarker).toHaveBeenCalledWith(removed);
    expect(removed.node).not.toBeInTheDocument();
    expect(sdk.setCamera).toHaveBeenCalledTimes(2);
});

it("keeps the schematic usable when authorization fails", async () => {
    vi.stubGlobal(
        "fetch",
        vi
            .fn()
            .mockResolvedValue(
                new Response(
                    JSON.stringify({ detail: "Map token unavailable" }),
                    { status: 503 },
                ),
            ),
    );
    render(<MapView {...props} mapsAvailable />);
    expect(
        await screen.findByText("Map token unavailable"),
    ).toBeInTheDocument();
    expect(
        screen.getByRole("group", { name: /Coordinate schematic/ }),
    ).toBeInTheDocument();
    fireEvent.click(
        screen.getAllByRole("button", { name: /^Select route / })[0],
    );
    expect(props.onSelect).toHaveBeenCalledWith(run.routes[0].id);
    expect(sdk.construct).not.toHaveBeenCalled();
});

it("refreshes expiring tokens and disposes the map if refreshed authorization fails", async () => {
    vi.stubGlobal(
        "fetch",
        vi
            .fn()
            .mockResolvedValueOnce(
                new Response(
                    JSON.stringify({
                        token: "expired-token",
                        client_id: "maps-client",
                        expires_on: "2000-01-01T00:00:00Z",
                    }),
                ),
            )
            .mockResolvedValueOnce(
                new Response(JSON.stringify({ detail: "Map token expired" }), {
                    status: 401,
                }),
            ),
    );
    render(<MapView {...props} mapsAvailable />);
    await ready();
    const resolve = vi.fn(),
        reject = vi.fn();
    act(() => sdk.options?.authOptions.getToken(resolve, reject));
    expect(await screen.findByText("Map token expired")).toBeInTheDocument();
    expect(reject).toHaveBeenCalled();
    expect(resolve).not.toHaveBeenCalled();
    await waitFor(() => expect(sdk.dispose).toHaveBeenCalledTimes(1));
    expect(
        screen.getByRole("group", { name: /Coordinate schematic/ }),
    ).toBeInTheDocument();
});

it("disposes a failing SDK map and offers facility selection in the fallback", async () => {
    render(<MapView {...props} mapsAvailable />);
    await ready();
    emit("error");
    expect(
        screen.getByRole("group", { name: /Coordinate schematic/ }),
    ).toBeInTheDocument();
    expect(sdk.dispose).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(
        screen.getByRole("button", {
            name: `Select facility ${scenario.locations[0].name}`,
        }),
        { key: " " },
    );
    expect(props.onSelectLocation).toHaveBeenCalledWith(
        scenario.locations[0].id,
    );
});

it("bounds loading and aborts a pending authorization request when the map cannot initialize", async () => {
    vi.useFakeTimers();
    let signal: AbortSignal | undefined;
    vi.stubGlobal(
        "fetch",
        vi.fn().mockImplementation((_url, options: RequestInit) => {
            signal = options.signal ?? undefined;
            return new Promise(() => {});
        }),
    );
    render(<MapView {...props} mapsAvailable />);
    await act(async () => {
        await Promise.resolve();
    });
    expect(signal?.aborted).toBe(false);
    await act(async () => {
        await vi.advanceTimersByTimeAsync(15000);
    });
    expect(
        screen.getByRole("group", { name: /Coordinate schematic/ }),
    ).toBeInTheDocument();
    expect(signal?.aborted).toBe(true);
    expect(sdk.construct).not.toHaveBeenCalled();
});

it("aborts pending authorization on unmount and never constructs a late SDK map", async () => {
    let resolve: ((response: Response) => void) | undefined;
    vi.stubGlobal(
        "fetch",
        vi.fn().mockImplementation(
            () =>
                new Promise<Response>((done) => {
                    resolve = done;
                }),
        ),
    );
    const view = render(<MapView {...props} mapsAvailable />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const signal = vi.mocked(fetch).mock.calls[0][1]?.signal as AbortSignal;
    view.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () =>
        resolve?.(
            new Response(
                JSON.stringify({
                    token: "late-token",
                    client_id: "maps-client",
                    expires_on: "2099-01-01T00:00:00Z",
                }),
            ),
        ),
    );
    expect(sdk.construct).not.toHaveBeenCalled();
});
