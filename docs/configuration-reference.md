# Configuration reference

Python reads application configuration through `pydantic-settings` in
`src/template_repository/config.py`. `.env` is for local development; Container
Apps receives environment variables and the Insights exporter secret from
Terraform. Never commit a populated `.env` or print the full azd environment.

## Application settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `APP_MODE` | `demo` | `demo`: memory/simulated routing; `live`: Azure Maps/Cosmos. No silent fallback. |
| `AZURE_ENVIRONMENT` | `development` | Development enables Uvicorn reload; containers use `production`. |
| `HOST`, `PORT` | `0.0.0.0`, `8000` | API bind address and port. |
| `LOG_LEVEL` | `INFO` | Structured stdout logging verbosity. |
| `AUTH_ENABLED` | `false` locally | Enforce user bearer tokens on data APIs; Terraform sets `true` in Azure. |
| `ENTRA_TENANT_ID` | unset | Single tenant allowed to issue user access tokens. |
| `ENTRA_CLIENT_ID` | unset | SPA/API app registration client ID, not a workload identity or Maps account ID. |
| `ENTRA_API_SCOPE` | unset | Fully qualified delegated `access_as_user` scope URI. |
| `AZURE_CLIENT_ID` | unset | API/job user-assigned managed identity client ID. |
| `ALLOW_DEVELOPER_CREDENTIALS` | `false` | Explicit opt-in to DefaultAzureCredential for local live-mode development. |
| `AZURE_MAPS_CLIENT_ID` | unset | Maps **account** client ID, not an identity client ID. |
| `AZURE_MAPS_ENDPOINT` | `https://atlas.microsoft.com` | Azure Maps service origin. |
| `MAPS_BROWSER_CLIENT_ID` | unset | Separate render/traffic managed identity attached to API for browser token brokerage. |
| `MAPS_ALLOWED_ORIGINS` | `[]` | JSON array of exact browser origins, including scheme and nonstandard port. |
| `COSMOS_ENDPOINT` | unset | Cosmos account HTTPS endpoint. |
| `COSMOS_DATABASE` | `supply-chain-routing` | Database name; deployment explicitly supplies `supply-chain`. |
| `COSMOS_CONTAINER` | `scenarios` | Pre-provisioned container with `/scenario_id` partition key and TTL enabled. |
| `SCENARIO_TTL_SECONDS` | `86400` | Scenario retention. |
| `SNAPSHOT_TTL_SECONDS` | `3600` | Run/geocode snapshot retention; must exceed run timeout by at least 60 seconds. |
| `MAPS_CACHE_SECONDS` | `300` | Route-cache freshness; zero disables caching. Refresh job bypasses it. |
| `RUN_TIMEOUT_SECONDS` | `180` | Bounded worker lease, maximum 600. |
| `MAX_CONCURRENT_RUNS` | `2` | In-process concurrent optimizations, maximum 5. |
| `REQUESTS_PER_MINUTE` | `120` | Per-process API request budget, excluding health probes. |
| `EXPENSIVE_REQUESTS_PER_MINUTE` | `10` | Shared per-process budget for scenario creation, seed, optimize, geocode, and map-token operations. |
| `MAX_REQUEST_BYTES` | `65536` | Maximum buffered request body, maximum 131072. |
| `MAX_MEMORY_DOCUMENTS` | `1000` | Demo-only memory repository document bound. |
| `TELEMETRY_ENABLED` | `false` | Opt into Azure Monitor OpenTelemetry export. |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | unset | Exporter configuration, kept in an ACA secret. |
| `REFRESH_ENABLED` | `false` | Explicit opt-in for the scheduled refresh entrypoint. |
| `REFRESH_MAX_SCENARIOS` | `5` | Maximum recently active scenarios refreshed per job execution, maximum 20. |

Keep the API at one replica until request budgets and worker claiming are
distributed. The current controls are demo safeguards, not global quotas or an
authorization system.

## Local frontend and web container

| Variable | Meaning |
| --- | --- |
| `API_PROXY_TARGET` | Vite proxy target, default `http://127.0.0.1:8000`. |
| `API_INTERNAL_URL` | Nginx's API origin without a trailing slash; default `http://api:8000`. |
| `E2E_API_PORT`, `E2E_WEB_PORT` | Optional isolated Playwright test ports, defaults 8000/5173. |

No Azure key or token belongs in a Vite environment variable or frontend
bundle. The browser requests short-lived render/traffic authorization from the
API. It cannot call Maps search, routing or weather services. Traffic overlays
require the explicit `Microsoft.Maps/accounts/services/traffic/read` data action.

React discovers nonsecret Entra configuration at `/api/auth/config`; no frontend
rebuild is required when deployment IDs change. MSAL obtains user access tokens
at runtime and sends them in Authorization headers, including SSE requests.
See [authentication](authentication.md) for redirects and local sign-in.

## Scenario limits and units

The public demo supports up to 10 suppliers and 3 factories and is bounded to
latitude **24..50**, longitude **-125..-66** (a contiguous-US bounding box, not a
country-border test). Start with synthetic Midwest seed locations. Address
results outside this box are excluded.

Supply/capacity is measured in shipment units, to three decimal places. Costs
use a scenario currency and explicit per-unit assumptions. The solver scales
quantities and objective coefficients to thousandths; excessive objective
ranges are rejected. Only one enabled fuel-price override is allowed.

Route duration includes traffic. Weather and injected facility delays are
additional modeled minutes. The cost model is described in
[architecture](../ARCHITECTURE.md).

## Terraform and azd

`infra/main.tfvars.json` is the visible source of deployment specifications.
azd substitutes `${PLACEHOLDER}` values; root Terraform outputs become azd
environment values.

Core context is `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID`, `AZURE_LOCATION`,
`AZURE_ENV_NAME`, `AZURE_RESOURCE_GROUP`, and `AZURE_PRINCIPAL_ID` (object ID).
Remote state uses `RS_RESOURCE_GROUP`, `RS_STORAGE_ACCOUNT`,
`RS_CONTAINER_NAME`, and `RS_PROJECT_NAME`.

Networking requires an explicit `PUBLIC_NETWORK_ACCESS_ENABLED` plus existing
subnet IDs when private. No resource group, VNet, subnet, or DNS zone is created.
See [deployment](deployment.md) for private/public examples, required identity
permissions, runtime outputs, and the refresh image synchronization hook.
