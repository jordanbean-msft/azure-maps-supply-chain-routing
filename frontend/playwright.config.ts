import { defineConfig, devices } from "@playwright/test";
import path from "node:path";

const apiPort = process.env.E2E_API_PORT ?? "8000";
const webPort = process.env.E2E_WEB_PORT ?? "5173";
const apiOrigin = `http://127.0.0.1:${apiPort}`;
const webOrigin = `http://127.0.0.1:${webPort}`;

export default defineConfig({
    testDir: "./e2e",
    fullyParallel: false,
    workers: 1,
    timeout: 60000,
    expect: { timeout: 15000 },
    reporter: [["list"], ["html", { open: "never" }]],
    use: { baseURL: webOrigin, trace: "retain-on-failure" },
    projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
    webServer: [
        {
            command: "uv run supply-chain-routing",
            cwd: path.resolve(import.meta.dirname, ".."),
            env: {
                APP_MODE: "demo",
                AZURE_ENVIRONMENT: "production",
                HOST: "127.0.0.1",
                PORT: apiPort,
            },
            url: `${apiOrigin}/health/ready`,
            timeout: 120000,
            reuseExistingServer: false,
        },
        {
            command: `npm run dev -- --host 127.0.0.1 --port ${webPort}`,
            env: { API_PROXY_TARGET: apiOrigin },
            url: webOrigin,
            timeout: 60000,
            reuseExistingServer: false,
        },
    ],
});
