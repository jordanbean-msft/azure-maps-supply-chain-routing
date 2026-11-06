/** Snake_case wire contracts matching src/template_repository/models.
 * Datetimes are timezone-aware ISO 8601 strings; coordinates are [longitude, latitude].
 */
export interface Location {
    id: string;
    name: string;
    kind: "supplier" | "factory";
    latitude: number;
    longitude: number;
    address: string;
    /** Supplier supply or factory capacity in units. */
    quantity: number;
}

export interface CostProfile {
    currency: string;
    distance_cost_per_km: number;
    driver_cost_per_hour: number;
    fuel_price_per_liter: number;
    fuel_liters_per_100_km: number;
    emissions_kg_per_liter: number;
    carbon_cost_per_kg: number;
    delay_penalty_per_hour: number;
}

export interface TruckProfile {
    height_m: number;
    width_m: number;
    length_m: number;
    weight_kg: number;
    max_speed_kph: number;
}

export interface Disruption {
    id: string;
    kind: "road_closure" | "facility_delay" | "weather" | "fuel_price";
    name: string;
    route_id: string | null;
    location_id: string | null;
    delay_minutes: number;
    severity: number;
    fuel_price_per_liter: number | null;
    enabled: boolean;
}

export interface Scenario {
    id: string;
    name: string;
    locations: Location[];
    cost_profile: CostProfile;
    disruptions: Disruption[];
    departure_time: string;
    truck: TruckProfile;
}

export interface RouteCandidate {
    id: string;
    supplier_id: string;
    factory_id: string;
    geometry: [number, number][];
    distance_km: number;
    /** Includes traffic, excludes weather and simulated delays. */
    duration_minutes: number;
    traffic_delay_minutes: number;
    weather_delay_minutes: number;
    simulated_delay_minutes: number;
    toll_estimate: number;
    weather_risk: number;
    source: "azure_maps" | "simulated";
}

export interface CostBreakdown {
    distance_cost: number;
    driver_time_cost: number;
    toll_cost: number;
    fuel_cost: number;
    carbon_cost: number;
    traffic_delay_penalty: number;
    weather_delay_penalty: number;
    simulated_disruption_penalty: number;
    total: number;
}

export interface Allocation {
    route_id: string;
    supplier_id: string;
    factory_id: string;
    quantity: number;
    unit_cost: CostBreakdown;
    total_cost: number;
}

export type RunStatus =
    "queued" | "running" | "completed" | "failed" | "infeasible";

export interface OptimizationRun {
    id: string;
    scenario_id: string;
    status: RunStatus;
    stage: string;
    progress: number;
    created_at: string;
    updated_at: string;
    routes: RouteCandidate[];
    allocations: Allocation[];
    total_cost: number;
    warnings: string[];
    error: string | null;
}

export interface RunEvent {
    sequence: number;
    run_id: string;
    status: RunStatus;
    stage: string;
    progress: number;
    message: string;
}

export interface AppConfig {
    mode: "demo" | "live";
    routing_source: "simulated" | "azure_maps";
    routing_available: boolean;
    maps_available: boolean;
    persistence: "memory" | "cosmos";
    max_suppliers: number;
    max_factories: number;
}

export interface MapsToken {
    token: string;
    client_id: string;
    expires_on: string;
}

export interface GeocodeRequest {
    address: string;
}

export interface GeocodeResult {
    address: string;
    latitude: number;
    longitude: number;
}

export interface ProblemDetails {
    type: string;
    title: string;
    status: number;
    detail: string;
    instance: string | null;
}
