export type MapTarget =
    | { kind: "route" | "facility"; id: string }
    | { kind: "network"; id: null };
