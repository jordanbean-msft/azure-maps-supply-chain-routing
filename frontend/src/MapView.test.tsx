import {
    act,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/react";
import { expect, it, vi } from "vitest";
import MapView from "./MapView";
import { run, scenario } from "./test-fixtures";

const sdk = vi.hoisted(() => ({
    events: new Map<string, (...args: unknown[]) => void>(),
    dispose: vi.fn(),
    setTraffic: vi.fn(),
    options: null as null | {
        authOptions: {
            getToken: (
                resolve: (token: string) => void,
                reject: (error: unknown) => void,
            ) => void;
            clientId: string;
        };
    },
    markers: [] as { getOptions: () => { position: number[] } }[],
}));

vi.mock("azure-maps-control", () => ({
    AuthenticationType: { anonymous: "anonymous" },
    ControlPosition: { TopRight: "top-right" },
    Map: class {
        constructor(_element: HTMLElement, options: typeof sdk.options) {
            sdk.options = options;
            sdk.events.clear();
            sdk.markers = [];
        }
        controls = { add: vi.fn() };
        sources = { add: vi.fn(), remove: vi.fn() };
        layers = { add: vi.fn(), remove: vi.fn() };
        markers = {
            add: (marker: (typeof sdk.markers)[number]) =>
                sdk.markers.push(marker),
            remove: vi.fn(),
        };
        events = {
            add: (name: string, ...args: unknown[]) =>
                sdk.events.set(
                    name,
                    args.at(-1) as (...args: unknown[]) => void,
                ),
            remove: vi.fn(),
        };
        dispose = sdk.dispose;
        setCamera = vi.fn();
        setTraffic = sdk.setTraffic;
    },
    HtmlMarker: class {
        getOptions = () => ({ position: [-84, 40] });
    },
    Shape: class {},
    source: {
        DataSource: class {
            add = vi.fn();
        },
    },
    layer: { LineLayer: class {} },
    data: {
        Feature: class {},
        LineString: class {},
        BoundingBox: { fromPositions: vi.fn() },
    },
    control: { ZoomControl: class {}, CompassControl: class {} },
}));

it("uses token/client-id auth, handles drag and traffic controls, and disposes the map", async () => {
    const fetch = vi.fn().mockResolvedValue(
        new Response(
            JSON.stringify({
                token: "short-lived-token",
                client_id: "maps-client",
                expires_on: "2099-01-01T00:00:00Z",
            }),
        ),
    );
    vi.stubGlobal("fetch", fetch);
    const move = vi.fn();
    const view = render(
        <MapView
            mapsAvailable
            locations={scenario.locations}
            routes={run.routes}
            selected="route-1"
            disabled={false}
            onMove={move}
            onSelect={vi.fn()}
        />,
    );
    await waitFor(() =>
        expect(sdk.options?.authOptions.clientId).toBe("maps-client"),
    );
    const resolve = vi.fn(),
        reject = vi.fn();
    await act(async () => {
        sdk.options?.authOptions.getToken(resolve, reject);
    });
    expect(resolve).toHaveBeenCalledWith("short-lived-token");
    expect(reject).not.toHaveBeenCalled();
    await act(async () => {
        sdk.events.get("ready")?.();
    });
    expect(sdk.markers).toHaveLength(2);
    act(() => {
        sdk.events.get("dragend")?.();
    });
    expect(move).toHaveBeenCalledWith(
        expect.objectContaining({ longitude: -84, latitude: 40 }),
    );
    fireEvent.click(screen.getByLabelText("Live traffic overlay"));
    expect(sdk.setTraffic).toHaveBeenLastCalledWith({
        flow: "relative",
        incidents: true,
    });
    view.unmount();
    expect(sdk.dispose).toHaveBeenCalled();
    const signal = fetch.mock.calls[0][1].signal as AbortSignal;
    expect(signal.aborted).toBe(true);
});

it("keeps coordinates and polylines usable when live map authorization fails", async () => {
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
    render(
        <MapView
            mapsAvailable
            locations={scenario.locations}
            routes={run.routes}
            selected="route-1"
            disabled={false}
            onMove={vi.fn()}
            onSelect={vi.fn()}
        />,
    );
    expect(
        await screen.findByText("Map token unavailable"),
    ).toBeInTheDocument();
    expect(
        screen.getByRole("img", { name: /Coordinate schematic/ }),
    ).toBeInTheDocument();
    expect(
        screen.getByRole("button", { name: "Select route route-1" }),
    ).toBeInTheDocument();
});
