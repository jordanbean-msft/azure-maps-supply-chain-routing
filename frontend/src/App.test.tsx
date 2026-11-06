import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import App from "./App";
import type { AppConfig } from "./types";

const config: AppConfig = {
    mode: "demo",
    routing_source: "simulated",
    routing_available: true,
    maps_available: false,
    persistence: "memory",
    max_suppliers: 10,
    max_factories: 3,
};

describe("API configuration", () => {
    it("labels demo data as simulated rather than live", async () => {
        const fetch = vi.fn().mockResolvedValue({
            ok: true,
            json: async () => config,
        });
        vi.stubGlobal("fetch", fetch);
        render(<App />);
        expect(
            await screen.findByText(/simulated routing/),
        ).toBeInTheDocument();
        expect(fetch).toHaveBeenCalledWith(
            "/api/config",
            expect.objectContaining({ signal: expect.any(AbortSignal) }),
        );
    });

    it("reports API errors instead of claiming availability", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue({ ok: false, status: 503 }),
        );
        render(<App />);
        expect(await screen.findByRole("alert")).toHaveTextContent("503");
    });

    it("does not imply live Maps is available when it is not initialized", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue({
                ok: true,
                json: async () => ({
                    ...config,
                    mode: "live",
                    maps_available: false,
                }),
            }),
        );
        render(<App />);
        expect(
            await screen.findByText(/Azure Maps not available/),
        ).toBeInTheDocument();
    });
});
