import { useEffect, useRef, useState } from "react";
import { Button, Checkbox } from "@fluentui/react-components";
import * as atlas from "azure-maps-control";
import "azure-maps-control/dist/atlas.min.css";
import { errorMessage, request } from "./api";
import type { MapTarget } from "./mapTarget";
import type {
    Allocation,
    Disruption,
    Location,
    MapsToken,
    RouteCandidate,
} from "./types";
import "./MapView.css";

interface Props {
    mapsAvailable: boolean;
    locations: Location[];
    routes: RouteCandidate[];
    allocations: Allocation[];
    selected: string | null;
    disabled: boolean;
    onSelect: (id: string) => void;
    onMove: (location: Location) => void;
    selectedLocation?: string | null;
    onSelectLocation?: (id: string) => void;
    target?: MapTarget | null;
    disruptions?: Disruption[];
}

interface DisplayProps extends Props {
    showAlternatives: boolean;
    animateRoute: boolean;
}

const BLUE = "#0078d4";
const PURPLE = "#5c2d91";
const PREVIEW = "#b4009e";
const SLATE = "#5c6873";
const TEAL = "#00796b";
const RED = "#c42b1c";
const ROUTE_ARROW = "M 10 0 L -8 -7 L -4 0 L -8 7 Z";

function laneName(route: RouteCandidate, locations: Location[]): string {
    const name = (id: string) =>
        locations.find((location) => location.id === id)?.name ?? id;
    return `${name(route.supplier_id)} → ${name(route.factory_id)}`;
}

function estimatedMinutes(route: RouteCandidate): number {
    return Math.round(
        route.duration_minutes +
            route.weather_delay_minutes +
            route.simulated_delay_minutes,
    );
}

function routeLabel(route: RouteCandidate, locations: Location[]): string {
    return `${laneName(route, locations)} · ${route.distance_km.toFixed(1)} km · ETA ${estimatedMinutes(route)} min · ${route.source === "simulated" ? "Simulated estimate" : "Azure Maps estimate"}`;
}

function routePreview(
    route: RouteCandidate,
    target?: MapTarget | null,
): boolean {
    return target?.kind === "route" && target.id === route.id;
}

function shipmentQuantity(route: RouteCandidate, props: Props): number {
    return props.allocations
        .filter((item) => item.route_id === route.id && item.quantity > 0)
        .reduce((sum, item) => sum + item.quantity, 0);
}

function shipmentLabel(route: RouteCandidate, props: Props): string {
    const quantity = shipmentQuantity(route, props);
    return quantity > 0
        ? `Recommended shipment · ${quantity.toLocaleString()} units`
        : "Unused alternative · no shipments";
}

function visibleRoutes(props: DisplayProps): RouteCandidate[] {
    return props.routes.filter(
        (route) =>
            props.showAlternatives ||
            shipmentQuantity(route, props) > 0 ||
            route.id === props.selected ||
            routePreview(route, props.target) ||
            closed(route, props.disruptions),
    );
}

function closed(
    route: RouteCandidate,
    disruptions: Disruption[] = [],
): boolean {
    return disruptions.some(
        (item) =>
            item.enabled &&
            item.kind === "road_closure" &&
            item.route_id === route.id,
    );
}

function facilityStatus(id: string, disruptions: Disruption[] = []): string {
    const delays = disruptions.filter(
        (item) =>
            item.enabled &&
            item.kind === "facility_delay" &&
            item.location_id === id,
    );
    return delays.length
        ? `ENABLED · DELAYED ${delays.reduce((sum, item) => sum + item.delay_minutes, 0)} min`
        : "";
}

function targetLabel(props: Props): string {
    if (!props.target) return "No disruption target selected";
    if (props.target.kind === "network")
        return `Entire network · all ${props.routes.length} routes affected${props.routes.length ? "" : " · no routes yet"}`;
    if (props.target.kind === "facility")
        return (
            props.locations.find((item) => item.id === props.target?.id)
                ?.name ?? "Facility no longer available"
        );
    const route = props.routes.find((item) => item.id === props.target?.id);
    return route
        ? laneName(route, props.locations)
        : "Route no longer available";
}

function popupContent(title: string, detail: string): HTMLElement {
    const content = document.createElement("div");
    content.className = "routing-map-popup";
    const heading = document.createElement("strong");
    heading.textContent = title;
    const description = document.createElement("p");
    description.textContent = detail;
    content.append(heading, description);
    return content;
}

function schematicNameLines(name: string): string[] {
    const lines: string[] = [];
    let remaining = name;
    while (remaining.length > 24) {
        const space = remaining.lastIndexOf(" ", 24);
        const end = space >= 12 ? space : 24;
        lines.push(remaining.slice(0, end));
        remaining = remaining.slice(end).trimStart();
    }
    return [...lines, remaining];
}

function Schematic(props: DisplayProps) {
    const { locations, routes, selected, onSelect, onSelectLocation, target } =
        props;
    const selectedRoute = routes.find((route) => route.id === selected);
    const points = [
        ...locations.map((item) => [item.longitude, item.latitude]),
        ...routes.flatMap((route) => route.geometry),
    ];
    const xs = points.map((point) => point[0]);
    const ys = points.map((point) => point[1]);
    const minX = xs.length ? Math.min(...xs) : -95.9;
    const maxX = xs.length ? Math.max(...xs) : -94.8;
    const minY = ys.length ? Math.min(...ys) : 29.3;
    const maxY = ys.length ? Math.max(...ys) : 30.2;
    const project = ([lon, lat]: number[]) => [
        110 + ((lon - minX) / (maxX - minX || 1)) * 580,
        300 - ((lat - minY) / (maxY - minY || 1)) * 200,
    ];
    const activate = (event: React.KeyboardEvent, action: () => void) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            action();
        }
    };
    return (
        <svg
            viewBox="0 0 800 400"
            className="schematic"
            aria-label="Coordinate schematic, not a basemap"
            role="group"
        >
            <rect width="800" height="400" fill="#fafafa" />
            <text x="20" y="28" className="schematic-label">
                COORDINATE SCHEMATIC · NO BASEMAP
            </text>
            {!points.length && (
                <g>
                    <text
                        x="400"
                        y="190"
                        textAnchor="middle"
                        className="point-label"
                    >
                        Houston region · 29.7604° N, 95.3698° W
                    </text>
                    <text
                        x="400"
                        y="215"
                        textAnchor="middle"
                        className="coordinate-label"
                    >
                        Add facilities to display your network
                    </text>
                </g>
            )}
            {visibleRoutes(props)
                .sort(
                    (a, b) =>
                        Number(a.id === selected) - Number(b.id === selected) ||
                        Number(shipmentQuantity(a, props) > 0) -
                            Number(shipmentQuantity(b, props) > 0),
                )
                .map((route) => {
                    const preview = routePreview(route, target);
                    const closure = closed(route, props.disruptions);
                    const quantity = shipmentQuantity(route, props);
                    const inspected = selected === route.id;
                    const label = `${shipmentLabel(route, props)} · ${routeLabel(route, locations)}`;
                    const midpoint =
                        route.geometry[Math.floor(route.geometry.length / 2)];
                    const [x, y] = midpoint ? project(midpoint) : [400, 200];
                    const polyline = route.geometry
                        .map((point) => project(point).join(","))
                        .join(" ");
                    return (
                        <g
                            key={route.id}
                            role="button"
                            tabIndex={0}
                            aria-label={`Select route ${route.id}`}
                            aria-description={`${label}${preview ? " · TARGET PREVIEW" : ""}${closure ? " · ENABLED · CLOSED" : ""}`}
                            aria-pressed={selected === route.id}
                            onClick={() => onSelect(route.id)}
                            onKeyDown={(event) =>
                                activate(event, () => onSelect(route.id))
                            }
                        >
                            <title>{label}</title>
                            <polyline
                                points={polyline}
                                fill="none"
                                stroke="#ffffff"
                                strokeWidth={preview ? 16 : inspected ? 11 : 9}
                            />
                            {preview && (
                                <polyline
                                    points={polyline}
                                    fill="none"
                                    stroke={PREVIEW}
                                    strokeWidth={13}
                                    strokeDasharray="9 5"
                                />
                            )}
                            {closure && (
                                <polyline
                                    points={polyline}
                                    fill="none"
                                    stroke={RED}
                                    strokeWidth={7}
                                    strokeDasharray="4 4"
                                />
                            )}
                            <polyline
                                points={polyline}
                                fill="none"
                                stroke={
                                    inspected
                                        ? PURPLE
                                        : quantity > 0
                                          ? BLUE
                                          : SLATE
                                }
                                strokeWidth={inspected || quantity > 0 ? 5 : 2}
                                strokeDasharray={
                                    inspected || quantity > 0
                                        ? undefined
                                        : "6 4"
                                }
                            />
                            {inspected && route.geometry.length > 1 && (
                                <g
                                    key={route.id}
                                    className={`route-motion-follower${props.animateRoute ? " is-moving" : ""}`}
                                    style={{
                                        offsetPath: `path("M ${route.geometry
                                            .map((point) =>
                                                project(point).join(","),
                                            )
                                            .join(" L ")}")`,
                                    }}
                                    aria-hidden="true"
                                >
                                    <path
                                        d={ROUTE_ARROW}
                                        className="route-direction-arrow"
                                    />
                                </g>
                            )}
                            <text
                                x={x}
                                y={y - 36}
                                textAnchor="middle"
                                className="lane-label"
                                visibility={
                                    inspected || quantity > 0
                                        ? undefined
                                        : "hidden"
                                }
                            >
                                {quantity > 0
                                    ? `${quantity.toLocaleString()} units`
                                    : "No shipments"}
                            </text>
                        </g>
                    );
                })}
            {locations.map((location) => {
                const [x, y] = project([location.longitude, location.latitude]);
                const anchor = x < 300 ? "start" : x > 500 ? "end" : "middle";
                const endpoint =
                    selectedRoute?.supplier_id === location.id
                        ? "START"
                        : selectedRoute?.factory_id === location.id
                          ? "END"
                          : null;
                const nameLines = schematicNameLines(
                    `${endpoint ? `${endpoint} · ` : ""}${location.name}`,
                );
                const labelY = Math.max(
                    32,
                    y - 24 - (nameLines.length - 1) * 28,
                );
                const preview =
                    target?.kind === "facility" && target.id === location.id;
                const status = facilityStatus(location.id, props.disruptions);
                return (
                    <g
                        key={location.id}
                        className={`schematic-facility${endpoint ? " route-endpoint" : ""}`}
                        role="button"
                        tabIndex={0}
                        aria-label={`Select facility ${location.name}`}
                        aria-description={`${location.kind}${endpoint ? ` · Route ${endpoint}` : ""}${preview ? " · TARGET PREVIEW" : ""}${status ? ` · ${status}` : ""}`}
                        aria-pressed={props.selectedLocation === location.id}
                        onClick={() => onSelectLocation?.(location.id)}
                        onKeyDown={(event) =>
                            activate(event, () =>
                                onSelectLocation?.(location.id),
                            )
                        }
                    >
                        <title>
                            {location.name}: {location.latitude},{" "}
                            {location.longitude}
                        </title>
                        {endpoint && (
                            <circle
                                cx={x}
                                cy={y}
                                r={14}
                                fill="none"
                                stroke={PURPLE}
                                strokeWidth={3}
                            />
                        )}
                        {(preview ||
                            props.selectedLocation === location.id) && (
                            <circle
                                cx={x}
                                cy={y}
                                r={17}
                                fill="none"
                                stroke={preview ? PREVIEW : PURPLE}
                                strokeWidth={3}
                                strokeDasharray={preview ? "4 3" : undefined}
                            />
                        )}
                        {location.kind === "supplier" ? (
                            <circle cx={x} cy={y} r={9} fill={TEAL} />
                        ) : (
                            <rect
                                x={x - 9}
                                y={y - 9}
                                width={18}
                                height={18}
                                fill="#424242"
                            />
                        )}
                        <text
                            x={x}
                            y={labelY}
                            textAnchor={anchor}
                            className="point-label"
                        >
                            {nameLines.map((line, index) => (
                                <tspan x={x} dy={index ? 28 : 0} key={index}>
                                    {line}
                                </tspan>
                            ))}
                        </text>
                        <text
                            x={x}
                            y={y + 32}
                            textAnchor={anchor}
                            className="coordinate-label"
                        >
                            {location.latitude.toFixed(3)},{" "}
                            {location.longitude.toFixed(3)}
                        </text>
                        <text
                            x={x}
                            y={y + 49}
                            textAnchor={anchor}
                            className="lane-state"
                        >
                            {[preview && "TARGET PREVIEW", status]
                                .filter(Boolean)
                                .join(" · ")}
                        </text>
                    </g>
                );
            })}
            <text x="20" y="382" className="coordinate-label">
                Relative coordinates only · Use location editor to change
                coordinates
            </text>
        </svg>
    );
}

interface MarkerEntry {
    marker: atlas.HtmlMarker;
    node: HTMLButtonElement;
    click: () => void;
    drag: () => void;
}

interface MapResources {
    sources: atlas.source.DataSource[];
    layers: (atlas.layer.LineLayer | atlas.layer.SymbolLayer)[];
    popup: atlas.Popup;
    markers: Map<string, MarkerEntry>;
    topology: string | null;
    motion: {
        marker: atlas.HtmlMarker;
        node: HTMLDivElement;
        arrow: SVGSVGElement;
        added: boolean;
    };
}

function fit(map: atlas.Map, positions: number[][]): void {
    if (!positions.length) return;
    map.setCamera({
        bounds: atlas.data.BoundingBox.fromPositions(positions),
        padding: 75,
        maxZoom: 13,
        type: "ease",
    });
}

function networkPositions(props: Props): number[][] {
    return [
        ...props.locations.map((item) => [item.longitude, item.latitude]),
        ...props.routes.flatMap((route) => route.geometry),
    ];
}

function AzureMap(
    props: DisplayProps & { onError: (message: string) => void },
) {
    const container = useRef<HTMLDivElement>(null);
    const mapRef = useRef<atlas.Map | null>(null);
    const resources = useRef<MapResources | null>(null);
    const latest = useRef(props);
    const [ready, setReady] = useState(false);
    const [traffic, setTraffic] = useState(false);
    useEffect(() => {
        latest.current = props;
    });

    useEffect(() => {
        const controller = new AbortController();
        let map: atlas.Map | null = null;
        const readyTimeout = window.setTimeout(() => {
            latest.current.onError(
                "Azure Maps took too long to load. Showing the coordinate schematic instead.",
            );
            controller.abort();
        }, 15000);
        const handleError = () => {
            if (!controller.signal.aborted)
                latest.current.onError(
                    "Azure Maps could not load. The coordinate schematic remains available.",
                );
        };
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
            const id: unknown =
                shape instanceof atlas.Shape
                    ? shape.getProperties().route_id
                    : shape && "properties" in shape
                      ? shape.properties?.route_id
                      : null;
            const route = latest.current.routes.find((item) => item.id === id);
            if (!route || !map || !resources.current) return;
            latest.current.onSelect(route.id);
            resources.current.popup.setOptions({
                position: event.position,
                content: popupContent(
                    laneName(route, latest.current.locations),
                    `${shipmentLabel(route, latest.current)} · ${routeLabel(route, latest.current.locations)}${closed(route, latest.current.disruptions) ? " · ENABLED · CLOSED (simulation)" : ""} · Inspection does not change the shipment plan.`,
                ),
            });
            resources.current.popup.open(map);
        };
        const handleReady = () => {
            if (controller.signal.aborted || !map || resources.current) return;
            window.clearTimeout(readyTimeout);
            const sources = Array.from(
                { length: 5 },
                () => new atlas.source.DataSource(),
            );
            map.sources.add(sources);
            const layers = [
                new atlas.layer.LineLayer(sources[0], undefined, {
                    strokeColor: "#ffffff",
                    strokeWidth: 6,
                }),
                new atlas.layer.LineLayer(sources[0], undefined, {
                    strokeColor: SLATE,
                    strokeWidth: 2,
                    strokeDashArray: [3, 3],
                }),
                new atlas.layer.LineLayer(sources[4], undefined, {
                    strokeColor: "#ffffff",
                    strokeWidth: 10,
                }),
                new atlas.layer.LineLayer(sources[4], undefined, {
                    strokeColor: BLUE,
                    strokeWidth: 6,
                }),
                new atlas.layer.LineLayer(sources[3], undefined, {
                    strokeColor: "#ffffff",
                    strokeWidth: 12,
                }),
                new atlas.layer.LineLayer(sources[3], undefined, {
                    strokeColor: RED,
                    strokeWidth: 7,
                    strokeDashArray: [1, 1],
                }),
                new atlas.layer.LineLayer(sources[2], undefined, {
                    strokeColor: "#ffffff",
                    strokeWidth: 16,
                }),
                new atlas.layer.LineLayer(sources[2], undefined, {
                    strokeColor: PREVIEW,
                    strokeWidth: 13,
                    strokeDashArray: [3, 2],
                }),
                new atlas.layer.LineLayer(sources[1], undefined, {
                    strokeColor: "#ffffff",
                    strokeWidth: 10,
                }),
                new atlas.layer.LineLayer(sources[1], undefined, {
                    strokeColor: PURPLE,
                    strokeWidth: 6,
                }),
                new atlas.layer.SymbolLayer(sources[4], undefined, {
                    placement: "line-center",
                    iconOptions: { image: "none" },
                    textOptions: {
                        textField: ["get", "shipment_label"],
                        size: 14,
                        color: "#004578",
                        haloColor: "#ffffff",
                        haloWidth: 3,
                        offset: [0, -1.2],
                    },
                }),
                new atlas.layer.SymbolLayer(sources[1], undefined, {
                    placement: "line-center",
                    iconOptions: { image: "none" },
                    textOptions: {
                        textField: ["get", "shipment_label"],
                        size: 14,
                        color: PURPLE,
                        haloColor: "#ffffff",
                        haloWidth: 3,
                        offset: [0, -1.5],
                    },
                }),
            ];
            map.layers.add(layers);
            layers.forEach((layer) =>
                map?.events.add("click", layer, selectRoute),
            );
            const node = document.createElement("div");
            node.className = "route-motion-marker";
            node.hidden = true;
            node.setAttribute("aria-hidden", "true");
            node.innerHTML = `<svg viewBox="-12 -12 24 24"><path class="route-direction-arrow" d="${ROUTE_ARROW}"/></svg>`;
            const marker = new atlas.HtmlMarker({
                htmlContent: node,
                anchor: "center",
                draggable: false,
            });
            resources.current = {
                sources,
                layers,
                popup: new atlas.Popup({ closeButton: true }),
                markers: new Map(),
                topology: null,
                motion: {
                    marker,
                    node,
                    arrow: node.querySelector("svg")!,
                    added: false,
                },
            };
            setReady(true);
        };
        const initialize = async () => {
            let token = (
                await request<MapsToken>("/maps/token", {
                    signal: controller.signal,
                })
            ).data;
            if (controller.signal.aborted || !container.current) return;
            map = new atlas.Map(container.current, {
                center: [-95.3698, 29.7604],
                zoom: 9,
                style: "grayscale_light",
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
                                latest.current.onError(errorMessage(error));
                        });
                    },
                },
            });
            mapRef.current = map;
            map.controls.add(
                [
                    new atlas.control.ZoomControl(),
                    new atlas.control.CompassControl(),
                    new atlas.control.StyleControl({
                        mapStyles: [
                            "grayscale_light",
                            "road",
                            "satellite_road_labels",
                        ],
                    }),
                ],
                { position: atlas.ControlPosition.TopRight },
            );
            map.events.add("ready", handleReady);
            map.events.add("error", handleError);
        };
        void initialize().catch((error: unknown) => {
            if (!controller.signal.aborted)
                latest.current.onError(errorMessage(error));
        });
        const observer =
            typeof ResizeObserver === "undefined"
                ? null
                : new ResizeObserver(() => map?.resize());
        if (container.current) observer?.observe(container.current);
        return () => {
            controller.abort();
            window.clearTimeout(readyTimeout);
            observer?.disconnect();
            if (map) {
                map.events.remove("ready", handleReady);
                map.events.remove("error", handleError);
                const current = resources.current;
                if (current) {
                    current.markers.forEach(({ marker, node, click, drag }) => {
                        node.removeEventListener("click", click);
                        map?.events.remove("dragend", marker, drag);
                        map?.markers.remove(marker);
                    });
                    current.layers.forEach((layer) =>
                        map?.events.remove("click", layer, selectRoute),
                    );
                    current.popup.remove();
                    map.markers.remove(current.motion.marker);
                    map.layers.remove(current.layers);
                    current.sources.forEach((source) =>
                        map?.sources.remove(source),
                    );
                }
                map.dispose();
            }
            resources.current = null;
            mapRef.current = null;
        };
    }, []);

    useEffect(() => {
        const map = mapRef.current;
        const current = resources.current;
        if (!ready || !map || !current) return;
        const groups = [
            visibleRoutes(props).filter(
                (route) => shipmentQuantity(route, props) === 0,
            ),
            props.routes.filter((route) => route.id === props.selected),
            props.routes.filter((route) => routePreview(route, props.target)),
            props.routes.filter((route) => closed(route, props.disruptions)),
            props.routes.filter((route) => shipmentQuantity(route, props) > 0),
        ];
        groups.forEach((routes, index) => {
            current.sources[index].setShapes(
                routes.map(
                    (route) =>
                        new atlas.data.Feature(
                            new atlas.data.LineString(route.geometry),
                            {
                                route_id: route.id,
                                label: `${shipmentLabel(route, props)} · ${route.distance_km.toFixed(1)} km · ${estimatedMinutes(route)} min`,
                                shipment_label:
                                    route.id === props.selected && index !== 1
                                        ? ""
                                        : shipmentQuantity(route, props) > 0
                                          ? `${shipmentQuantity(route, props).toLocaleString()} units`
                                          : "No shipments",
                            },
                        ),
                ),
            );
        });
        current.markers.forEach((entry, id) => {
            if (props.locations.some((item) => item.id === id)) return;
            entry.node.removeEventListener("click", entry.click);
            map.events.remove("dragend", entry.marker, entry.drag);
            map.markers.remove(entry.marker);
            current.markers.delete(id);
        });
        props.locations.forEach((location) => {
            let entry = current.markers.get(location.id);
            if (!entry) {
                const node = document.createElement("button");
                node.type = "button";
                const marker = new atlas.HtmlMarker({ htmlContent: node });
                const click = () => {
                    const item = latest.current.locations.find(
                        (item) => item.id === location.id,
                    );
                    if (!item) return;
                    latest.current.onSelectLocation?.(item.id);
                    current.popup.setOptions({
                        position: [item.longitude, item.latitude],
                        content: popupContent(
                            item.name,
                            `${item.kind} · ${item.latitude.toFixed(4)}, ${item.longitude.toFixed(4)} · ${facilityStatus(item.id, latest.current.disruptions) || "No enabled facility delay"}${latest.current.disabled ? " · Coordinate editing locked" : " · Drag marker or use coordinate inputs to move"}`,
                        ),
                    });
                    current.popup.open(map);
                };
                const drag = () => {
                    const item = latest.current.locations.find(
                        (item) => item.id === location.id,
                    );
                    const position = marker.getOptions().position;
                    if (item && position && !latest.current.disabled)
                        latest.current.onMove({
                            ...item,
                            longitude: position[0],
                            latitude: position[1],
                        });
                };
                node.addEventListener("click", click);
                map.events.add("dragend", marker, drag);
                map.markers.add(marker);
                entry = { marker, node, click, drag };
                current.markers.set(location.id, entry);
            }
            const preview =
                props.target?.kind === "facility" &&
                props.target.id === location.id;
            const inspected = props.selectedLocation === location.id;
            const selectedRoute = props.routes.find(
                (route) => route.id === props.selected,
            );
            const endpoint =
                selectedRoute?.supplier_id === location.id
                    ? "START"
                    : selectedRoute?.factory_id === location.id
                      ? "END"
                      : null;
            const status = facilityStatus(location.id, props.disruptions);
            entry.node.className = `routing-map-marker ${location.kind}${endpoint ? " route-endpoint" : ""}${preview ? " is-preview" : ""}${inspected ? " is-inspected" : ""}${status ? " is-delayed" : ""}`;
            entry.node.textContent = `${endpoint ? `${endpoint} · ` : ""}${location.kind === "supplier" ? "●" : "■"} ${location.name}${preview ? " · TARGET PREVIEW" : ""}${status ? ` · ${status}` : ""}`;
            entry.node.setAttribute(
                "aria-label",
                `Select facility ${location.name}`,
            );
            entry.node.setAttribute(
                "aria-description",
                `${location.kind}${endpoint ? ` · Route ${endpoint}` : ""}${preview ? " · TARGET PREVIEW" : ""}${status ? ` · ${status}` : ""}`,
            );
            entry.node.setAttribute("aria-pressed", String(inspected));
            entry.marker.setOptions({
                position: [location.longitude, location.latitude],
                draggable: !props.disabled,
            });
        });
        if (!current.motion.added) {
            map.markers.add(current.motion.marker);
            current.motion.added = true;
        }
        // Only coordinate/topology changes fit automatically; inspection and preview never move the camera.
        const topology = JSON.stringify({
            locations: props.locations.map((item) => [
                item.id,
                item.longitude,
                item.latitude,
            ]),
            routes: props.routes.map((item) => [item.id, item.geometry]),
        });
        if (current.topology !== topology) {
            fit(map, networkPositions(props));
            current.topology = topology;
            current.popup.close();
        }
    }, [ready, props]);

    const selectedRoute = props.routes.find(
        (item) => item.id === props.selected,
    );
    useEffect(() => {
        const map = mapRef.current;
        const motion = resources.current?.motion;
        if (!ready || !map || !motion) return;
        const geometry = selectedRoute?.geometry;
        motion.node.toggleAttribute("hidden", !geometry || geometry.length < 2);
        if (!geometry || geometry.length < 2) return;
        const length = atlas.math.getLengthOfPath(geometry, "meters");
        if (length <= 0) {
            motion.node.setAttribute("hidden", "");
            return;
        }
        let frame = 0;
        let start: number | null = null;
        let progress = props.animateRoute ? 0 : 0.5;
        const draw = () => {
            const position = atlas.math.getPositionAlongPath(
                geometry,
                length * progress,
                "meters",
            );
            const ahead = atlas.math.getPositionAlongPath(
                geometry,
                Math.min(
                    length,
                    length * progress + Math.max(1, length / 1000),
                ),
                "meters",
            );
            const [from, to] = map.positionsToPixels([position, ahead]);
            if (from && to) {
                const angle =
                    (Math.atan2(to[1] - from[1], to[0] - from[0]) * 180) /
                    Math.PI;
                motion.arrow.style.setProperty(
                    "transform",
                    `rotate(${angle}deg)`,
                );
            }
            motion.marker.setOptions({ position });
        };
        const tick = (time: number) => {
            start ??= time;
            if (document.visibilityState !== "hidden") {
                progress = ((time - start) % 6000) / 6000;
                draw();
            }
            frame = requestAnimationFrame(tick);
        };
        draw();
        map.events.add("move", draw);
        if (props.animateRoute) frame = requestAnimationFrame(tick);
        return () => {
            cancelAnimationFrame(frame);
            if (mapRef.current === map) map.events.remove("move", draw);
        };
    }, [ready, selectedRoute, props.animateRoute]);

    useEffect(() => {
        if (ready)
            mapRef.current?.setTraffic({
                flow: traffic ? "relative" : "none",
                incidents: traffic,
            });
    }, [ready, traffic]);

    const selectedFacility = props.locations.find(
        (item) => item.id === props.selectedLocation,
    );
    return (
        <div className="live-map">
            <div
                className="map-toolbar"
                role="toolbar"
                aria-label="Map controls"
            >
                <Button
                    size="small"
                    disabled={!ready || !networkPositions(props).length}
                    onClick={() =>
                        mapRef.current &&
                        fit(mapRef.current, networkPositions(props))
                    }
                >
                    Fit network
                </Button>
                <Button
                    size="small"
                    disabled={
                        !ready ||
                        (!selectedFacility && !selectedRoute?.geometry.length)
                    }
                    onClick={() => {
                        if (!mapRef.current) return;
                        if (selectedFacility)
                            mapRef.current.setCamera({
                                center: [
                                    selectedFacility.longitude,
                                    selectedFacility.latitude,
                                ],
                                zoom: 13,
                                type: "ease",
                            });
                        else if (selectedRoute)
                            fit(mapRef.current, selectedRoute.geometry);
                    }}
                >
                    Fit selected
                </Button>
                <Checkbox
                    label="Live traffic overlay"
                    checked={traffic}
                    onChange={(_, data) => setTraffic(data.checked === true)}
                />
                <span>Light / road / satellite in map style control</span>
            </div>
            <div
                ref={container}
                className="atlas-map"
                aria-label="Azure Maps route map"
            />
        </div>
    );
}

export default function MapView(props: Props) {
    const [failure, setFailure] = useState<string | null>(null);
    const [showAlternatives, setShowAlternatives] = useState(false);
    const [animateRoute, setAnimateRoute] = useState(true);
    const [reducedMotion, setReducedMotion] = useState(
        () =>
            window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ??
            false,
    );
    useEffect(() => {
        const preference = window.matchMedia?.(
            "(prefers-reduced-motion: reduce)",
        );
        if (!preference) return;
        const update = () => setReducedMotion(preference.matches);
        update();
        preference.addEventListener("change", update);
        return () => preference.removeEventListener("change", update);
    }, []);
    const display = {
        ...props,
        showAlternatives,
        animateRoute: animateRoute && !reducedMotion,
    };
    const live = props.mapsAvailable && !failure;
    const recommended = props.routes.filter(
        (route) => shipmentQuantity(route, props) > 0,
    );
    const alternativeCount = props.routes.length - recommended.length;
    const enabledGlobal =
        props.disruptions?.filter(
            (item) =>
                item.enabled &&
                (item.kind === "weather" || item.kind === "fuel_price"),
        ) ?? [];
    const selectedRoute = props.routes.find(
        (item) => item.id === props.selected,
    );
    return (
        <section className="map-panel" aria-labelledby="map-title">
            <header className="map-heading">
                <h2 id="map-title">Shipment plan map</h2>
                <span>{live ? "Azure Maps" : "Coordinate schematic"}</span>
            </header>
            {failure && (
                <p role="status" className="map-notice">
                    {failure}
                </p>
            )}
            <div className="map-route-controls">
                <Checkbox
                    label={`Show unused alternatives (${alternativeCount})`}
                    checked={showAlternatives}
                    onChange={(_, data) =>
                        setShowAlternatives(data.checked === true)
                    }
                />
                <span>
                    {recommended.length} recommended{" "}
                    {recommended.length === 1 ? "route" : "routes"} · Blue lines
                    carry shipments; labels show units.
                </span>
                {selectedRoute && (
                    <Checkbox
                        label="Animate selected route"
                        checked={display.animateRoute}
                        disabled={reducedMotion}
                        onChange={(_, data) =>
                            setAnimateRoute(data.checked === true)
                        }
                    />
                )}
            </div>
            {selectedRoute && (
                <p
                    className="map-direction-summary"
                    role="status"
                    aria-label="Selected route direction"
                >
                    <strong>START · Supplier:</strong>{" "}
                    {props.locations.find(
                        (item) => item.id === selectedRoute.supplier_id,
                    )?.name ?? selectedRoute.supplier_id}
                    {" → "}
                    <strong>END · Factory:</strong>{" "}
                    {props.locations.find(
                        (item) => item.id === selectedRoute.factory_id,
                    )?.name ?? selectedRoute.factory_id}
                    {". "}
                    {display.animateRoute
                        ? "The arrow moves from start to end."
                        : "Static arrow shows travel direction."}{" "}
                    This is not live vehicle tracking.
                    {reducedMotion && " Reduced motion is enabled."}
                </p>
            )}
            {props.target && (
                <div className="map-target-status has-target" role="status">
                    TARGET PREVIEW · {targetLabel(props)}
                    {props.target.kind === "network" &&
                        " · Route colors still show the shipment plan."}
                </div>
            )}
            {!props.routes.length && (
                <p className="map-notice">
                    No routes yet. Save and calculate a shipment plan to see
                    recommended routes.
                </p>
            )}
            {enabledGlobal.length > 0 && (
                <p className="map-applied-status">
                    ENABLED · ENTIRE NETWORK ·{" "}
                    {enabledGlobal.map((item) => item.name).join(", ")} · all{" "}
                    {props.routes.length} routes affected
                    {props.routes.length ? "" : " · no routes yet"}
                </p>
            )}
            {live ? (
                <AzureMap {...display} onError={setFailure} />
            ) : (
                <Schematic {...display} />
            )}
            <div className="map-legend" aria-label="Map legend">
                <span className="legend-supplier">● Supplier</span>
                <span>■ Factory</span>
                <span>
                    <i className="line-swatch recommended" aria-hidden="true" />
                    Recommended shipment
                </span>
                <span>
                    <i className="line-swatch inspected" aria-hidden="true" />
                    Inspecting only
                </span>
                <span>
                    <i className="line-swatch alternative" aria-hidden="true" />
                    Unused alternative
                </span>
                <span>
                    <i className="line-swatch preview" aria-hidden="true" />
                    Disruption target
                </span>
                <span className="legend-closed">
                    <i className="line-swatch closed" aria-hidden="true" />
                    Simulated closure
                </span>
                <span>DELAYED · Enabled facility delay</span>
            </div>
            {selectedRoute && (
                <p className="map-route-summary">
                    INSPECTED · {shipmentLabel(selectedRoute, props)} ·{" "}
                    {routeLabel(selectedRoute, props.locations)}
                    {closed(selectedRoute, props.disruptions)
                        ? " · ENABLED · CLOSED (simulation)"
                        : ""}
                    {" · "}Inspecting does not change the plan.
                </p>
            )}
            <p className="map-caption">
                {live
                    ? props.disabled
                        ? "Coordinate editing is locked. Select facilities or lanes to inspect."
                        : "Select facilities or lanes to inspect. Drag markers to edit coordinates, then save and optimize."
                    : `Select visible facilities or routes with mouse, Enter or Space. ${props.disabled ? "Coordinate editing is locked." : "Edit coordinates in the location editor."}`}{" "}
                Unused alternatives are hidden unless requested, inspected or
                targeted. Purple means inspection, not a new recommendation.
                Lines show the last successful run; facilities show editor
                coordinates. Disruptions are simulations, not live road
                closures. ETA includes traffic, estimated weather and simulated
                delays from the last run.
            </p>
        </section>
    );
}
