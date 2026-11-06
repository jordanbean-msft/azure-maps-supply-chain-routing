import { useEffect, useRef, useState } from "react";
import * as atlas from "azure-maps-control";
import "azure-maps-control/dist/atlas.min.css";
import { errorMessage, request } from "./api";
import type { Location, MapsToken, RouteCandidate } from "./types";

interface Props {
    mapsAvailable: boolean;
    locations: Location[];
    routes: RouteCandidate[];
    selected: string | null;
    disabled: boolean;
    onSelect: (id: string) => void;
    onMove: (location: Location) => void;
}

function Schematic({ locations, routes, selected, onSelect }: Props) {
    const points = [
        ...locations.map((item) => [item.longitude, item.latitude]),
        ...routes.flatMap((route) => route.geometry),
    ];
    const xs = points.map((point) => point[0]);
    const ys = points.map((point) => point[1]);
    const minX = xs.length ? Math.min(...xs) : -1,
        maxX = xs.length ? Math.max(...xs) : 1;
    const minY = ys.length ? Math.min(...ys) : -1,
        maxY = ys.length ? Math.max(...ys) : 1;
    const project = ([lon, lat]: number[]) => [
        90 + ((lon - minX) / (maxX - minX || 1)) * 620,
        320 - ((lat - minY) / (maxY - minY || 1)) * 240,
    ];
    return (
        <svg
            viewBox="0 0 800 400"
            className="schematic"
            aria-label="Coordinate schematic, not a basemap"
            role="img"
        >
            <defs>
                <pattern
                    id="grid"
                    width="40"
                    height="40"
                    patternUnits="userSpaceOnUse"
                >
                    <path
                        d="M 40 0 L 0 0 0 40"
                        fill="none"
                        stroke="#dee8ed"
                        strokeWidth="1"
                    />
                </pattern>
            </defs>
            <rect width="800" height="400" fill="url(#grid)" />
            <text x="20" y="28" className="schematic-label">
                COORDINATE SCHEMATIC · NO BASEMAP
            </text>
            {[...routes]
                .sort(
                    (a, b) =>
                        Number(a.id === selected) - Number(b.id === selected),
                )
                .map((route) => (
                    <g
                        key={route.id}
                        role="button"
                        tabIndex={0}
                        aria-label={`Select route ${route.id}`}
                        onClick={() => onSelect(route.id)}
                        onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                onSelect(route.id);
                            }
                        }}
                    >
                        <title>
                            {route.id} · {route.source}
                        </title>
                        <polyline
                            points={route.geometry
                                .map((point) => project(point).join(","))
                                .join(" ")}
                            fill="none"
                            stroke={
                                route.id === selected ? "#006b76" : "#95aabd"
                            }
                            strokeWidth={route.id === selected ? 6 : 3}
                            strokeDasharray={
                                route.id === selected ? undefined : "7 5"
                            }
                        />
                    </g>
                ))}
            {locations.map((location) => {
                const [x, y] = project([location.longitude, location.latitude]);
                return (
                    <g key={location.id}>
                        <title>
                            {location.name}: {location.latitude},{" "}
                            {location.longitude}
                        </title>
                        {location.kind === "supplier" ? (
                            <circle
                                cx={x}
                                cy={y}
                                r={8}
                                fill="#006b76"
                                stroke="white"
                                strokeWidth={3}
                            />
                        ) : (
                            <rect
                                x={x - 8}
                                y={y - 8}
                                width={16}
                                height={16}
                                fill="#985214"
                                stroke="white"
                                strokeWidth={3}
                            />
                        )}
                        <text
                            x={x}
                            y={y - 17}
                            textAnchor="middle"
                            className="point-label"
                        >
                            {location.name}
                        </text>
                        <text
                            x={x}
                            y={y + 26}
                            textAnchor="middle"
                            className="coordinate-label"
                        >
                            {location.latitude.toFixed(3)},{" "}
                            {location.longitude.toFixed(3)}
                        </text>
                    </g>
                );
            })}
            <text x="20" y="382" className="coordinate-label">
                Longitude → · Latitude ↑ · Relative coordinates, not road or
                traffic imagery
            </text>
        </svg>
    );
}

function AzureMap({
    locations,
    routes,
    selected,
    disabled,
    onSelect,
    onMove,
    onError,
}: Props & { onError: (message: string) => void }) {
    const container = useRef<HTMLDivElement>(null);
    const mapRef = useRef<atlas.Map | null>(null);
    const [ready, setReady] = useState(false);
    const [traffic, setTraffic] = useState(false);
    const errorHandler = useRef(onError);
    useEffect(() => {
        errorHandler.current = onError;
    }, [onError]);

    useEffect(() => {
        const controller = new AbortController();
        let map: atlas.Map | null = null;
        const readyTimeout = window.setTimeout(() => {
            if (!controller.signal.aborted)
                errorHandler.current(
                    "Azure Maps took too long to load. Showing the coordinate schematic instead.",
                );
        }, 15000);
        const initialize = async () => {
            let token = (
                await request<MapsToken>("/maps/token", {
                    signal: controller.signal,
                })
            ).data;
            if (controller.signal.aborted || !container.current) return;
            map = new atlas.Map(container.current, {
                center: [-87.63, 41.88],
                zoom: 5,
                language: "en-US",
                authOptions: {
                    authType: atlas.AuthenticationType.anonymous,
                    clientId: token.client_id,
                    getToken: (resolve, reject) => {
                        const authorize = async () => {
                            if (
                                Date.parse(token.expires_on) - Date.now() <
                                60000
                            )
                                token = (
                                    await request<MapsToken>("/maps/token", {
                                        signal: controller.signal,
                                    })
                                ).data;
                            if (!controller.signal.aborted)
                                resolve(token.token);
                        };
                        void authorize().catch((error: unknown) => {
                            reject(error);
                            if (!controller.signal.aborted)
                                errorHandler.current(errorMessage(error));
                        });
                    },
                },
            });
            mapRef.current = map;
            map.controls.add(
                [
                    new atlas.control.ZoomControl(),
                    new atlas.control.CompassControl(),
                ],
                { position: atlas.ControlPosition.TopRight },
            );
            map.events.add("ready", () => {
                window.clearTimeout(readyTimeout);
                if (!controller.signal.aborted) setReady(true);
            });
            map.events.add("error", () => {
                if (!controller.signal.aborted)
                    errorHandler.current(
                        "Azure Maps could not load. The coordinate schematic remains available.",
                    );
            });
        };
        void initialize().catch((error: unknown) => {
            if (!controller.signal.aborted)
                errorHandler.current(errorMessage(error));
        });
        return () => {
            controller.abort();
            window.clearTimeout(readyTimeout);
            map?.dispose();
            mapRef.current = null;
        };
    }, []);

    useEffect(() => {
        const map = mapRef.current;
        if (!ready || !map) return;
        const all = new atlas.source.DataSource();
        const highlight = new atlas.source.DataSource();
        map.sources.add([all, highlight]);
        all.add(
            routes.map(
                (route) =>
                    new atlas.data.Feature(
                        new atlas.data.LineString(route.geometry),
                        { route_id: route.id },
                    ),
            ),
        );
        const selectedRoute = routes.find((route) => route.id === selected);
        if (selectedRoute)
            highlight.add(new atlas.data.LineString(selectedRoute.geometry));
        const line = new atlas.layer.LineLayer(all, undefined, {
            strokeColor: "#8199af",
            strokeWidth: 3,
        });
        const selectedLine = new atlas.layer.LineLayer(highlight, undefined, {
            strokeColor: "#006b76",
            strokeWidth: 7,
        });
        map.layers.add([line, selectedLine]);
        const selectRoute = (
            event:
                | atlas.MapMouseEvent
                | atlas.MapTouchEvent
                | atlas.MapMouseWheelEvent
                | atlas.layer.Layer
                | void,
        ) => {
            if (!event || !("shapes" in event)) return;
            const shape = event.shapes?.[0];
            if (shape instanceof atlas.Shape) {
                const id: unknown = shape.getProperties().route_id;
                if (typeof id === "string") onSelect(id);
            }
        };
        map.events.add("click", line, selectRoute);
        const markers = locations.map((location) => {
            const node = document.createElement("button");
            node.type = "button";
            node.className = `map-marker ${location.kind}`;
            node.textContent = location.kind === "supplier" ? "S" : "F";
            node.setAttribute(
                "aria-label",
                `${location.name}. Use coordinate inputs to move this ${location.kind}.`,
            );
            node.title = `${location.name} (${location.latitude}, ${location.longitude})`;
            const marker = new atlas.HtmlMarker({
                position: [location.longitude, location.latitude],
                htmlContent: node,
                draggable: !disabled,
            });
            map.markers.add(marker);
            map.events.add("dragend", marker, () => {
                const position = marker.getOptions().position;
                if (position)
                    onMove({
                        ...location,
                        longitude: position[0],
                        latitude: position[1],
                    });
            });
            return marker;
        });
        const positions = [
            ...locations.map((location) => [
                location.longitude,
                location.latitude,
            ]),
            ...routes.flatMap((route) => route.geometry),
        ];
        if (positions.length)
            map.setCamera({
                bounds: atlas.data.BoundingBox.fromPositions(positions),
                padding: 70,
                maxZoom: 12,
            });
        return () => {
            map.events.remove("click", line, selectRoute);
            markers.forEach((marker) => map.markers.remove(marker));
            map.layers.remove([line, selectedLine]);
            map.sources.remove(all);
            map.sources.remove(highlight);
        };
    }, [ready, locations, routes, selected, disabled, onMove, onSelect]);

    useEffect(() => {
        if (ready)
            mapRef.current?.setTraffic({
                flow: traffic ? "relative" : "none",
                incidents: traffic,
            });
    }, [ready, traffic]);

    return (
        <div className="live-map">
            <div
                ref={container}
                className="atlas-map"
                aria-label="Azure Maps route map"
            />
            <label className="traffic-toggle">
                <input
                    type="checkbox"
                    checked={traffic}
                    onChange={(event) => setTraffic(event.target.checked)}
                />{" "}
                Live traffic overlay
            </label>
        </div>
    );
}

export default function MapView(props: Props) {
    const [failure, setFailure] = useState<string | null>(null);
    return (
        <section className="panel map-panel" aria-labelledby="map-title">
            <div className="panel-heading">
                <div>
                    <p className="eyebrow">NETWORK VIEW</p>
                    <h2 id="map-title">Every lane, in context</h2>
                </div>
                <span className="badge">
                    {props.mapsAvailable && !failure
                        ? "Azure Maps"
                        : "Schematic"}
                </span>
            </div>
            {failure && (
                <p role="status" className="notice">
                    {failure}
                </p>
            )}
            {props.mapsAvailable && !failure ? (
                <AzureMap {...props} onError={setFailure} />
            ) : (
                <Schematic {...props} />
            )}
            <div className="map-legend">
                <span>● Supplier</span>
                <span>■ Factory</span>
                <span>━ Selected route</span>
                <span>┄ Alternative</span>
            </div>
            <p className="map-caption">
                {props.mapsAvailable && !failure
                    ? "Drag markers to edit coordinates, then save and optimize. Lines show the last successful run; markers show the editor. Azure Maps attribution and map controls are retained."
                    : "No live basemap is loaded. Lines show the last successful run; coordinate markers show the editor. Edit coordinates in the location editor, then save and optimize."}
            </p>
        </section>
    );
}
