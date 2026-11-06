import { useEffect, useState } from "react";
import { getConfig } from "./api";
import type { AppConfig } from "./types";
import "./style.css";

export default function App() {
    const [config, setConfig] = useState<AppConfig | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const controller = new AbortController();
        getConfig(controller.signal)
            .then(setConfig)
            .catch((failure: unknown) => {
                if (!controller.signal.aborted) {
                    setError(
                        failure instanceof Error
                            ? failure.message
                            : "API unavailable.",
                    );
                }
            });
        return () => controller.abort();
    }, []);

    return (
        <main>
            <h1>Supply Chain Routing</h1>
            <p>Supplier-to-factory lane planning with transparent costs.</p>
            {error ? (
                <p role="alert">{error} Start the API on port 8000.</p>
            ) : (
                <p role="status">
                    {config
                        ? config.mode === "demo"
                            ? "Demo mode — simulated routing, no live traffic or weather."
                            : `Live mode — Azure Maps ${config.maps_available ? "available" : "not available"}.`
                        : "Connecting to API…"}
                </p>
            )}
            <p>Scenario editing and optimization will be added next.</p>
        </main>
    );
}
