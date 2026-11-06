import type { AppConfig } from "./types";

export async function getConfig(signal?: AbortSignal): Promise<AppConfig> {
    const response = await fetch("/api/config", { signal });
    if (!response.ok) {
        throw new Error(
            `API configuration request failed (${response.status}).`,
        );
    }
    return response.json() as Promise<AppConfig>;
}
