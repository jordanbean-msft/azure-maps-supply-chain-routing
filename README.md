# Supply Chain Routing

A supplier-to-factory lane-planning demo using React/TypeScript and FastAPI,
targeting Azure Maps, Cosmos DB and Azure Container Apps.

**Foundation scaffold only:** domain contracts, health/config endpoints, and a
frontend that checks the API are implemented. Scenario editing, routing,
optimization, persistence and Azure infrastructure are subsequent workstreams.
See [the approved checklist](.github/plans/supply-chain-routing-demo.md).

## Local development (no Azure credentials)

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 22.13+
(22 LTS or 24 LTS recommended), and npm.

```bash
uv sync --extra dev
cp .env.example .env
npm --prefix frontend ci
uv run supply-chain-routing
```

In another terminal:

```bash
npm --prefix frontend run dev
```

Open http://localhost:5173. Vite proxies `/api` to http://localhost:8000.
`APP_MODE=demo` explicitly selects simulated routing and in-memory persistence;
the foundation does not yet execute routes or store scenarios. No live traffic,
weather or map basemap is claimed. `APP_MODE=live` remains unavailable (readiness
503) until the Azure service implementations are wired; it never silently falls
back to simulation.

- `GET /health` and `/health/live`: process liveness.
- `GET /health/ready`: demo readiness; future live dependency probes.
- `GET /api/config`: mode, routing/map availability and scenario limits.
- `GET /api/maps/token`: 503 until live authentication is implemented; future
  response is `{token, client_id, expires_on}` with a timezone-aware ISO timestamp.
- API docs: http://localhost:8000/docs.

Python imports remain `template_repository` and `uv run template-repository`
remains an alias for compatibility. Logs are JSON lines on stdout, configured at
startup without creating log files. Reload is enabled only with
`AZURE_ENVIRONMENT=development`; containers set it to `production`.

## Contracts and validation

Python wire models live in `src/template_repository/models/`; matching
TypeScript interfaces live in `frontend/src/types.ts`. JSON uses `snake_case`,
coordinates are `[longitude, latitude]`, quantities are supplier supply/factory
capacity, and timestamps include a timezone.

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest -W error
uv build
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run format:check
```

Use `uv run ruff format .` and `npm --prefix frontend run format` to format.
Repository-scoped VS Code tasks/debuggers in `.vscode/` cover setup, running,
packaging, tests, lint, formatting, types and infrastructure validation. The
existing `.code-workspace` delegates to these rather than duplicating tasks.

React/Vite and its test/lint toolchain are ecosystem dependencies; Microsoft does
not publish equivalent React build/testing tooling. Backend Azure SDKs and the
optimizer will be added by their implementation workstreams, not by foundation.

## Containers and Azure handoff

```bash
docker build -t supply-chain-api .
docker build -t supply-chain-web frontend
```

The API listens on `8000`. The non-root Nginx web container listens on `8080`;
set `API_INTERNAL_URL` to the API's internal origin **without a trailing slash**
(default `http://api:8000`). It proxies `/api/` and `/health` without stripping the
path, with buffering disabled and a long read timeout for SSE. Tokens are issued
server-side only; no service key belongs in frontend environment variables.

`azure.yaml` maps services `api` (root) and `web` (`frontend`) to Container Apps.
The infrastructure workstream must tag apps with `azd-service-name=api|web`, expose
only web publicly, configure managed identity/roles, inject runtime environment
variables, and provision Cosmos with `/scenario_id` as partition key. Existing
Terraform remains unchanged. Azure CLI, azd and Terraform are needed only for
later Azure work; **the scaffold is not ready for deployment**.

Infrastructure validation (after reviewing existing instructions):

```bash
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
```

## License and disclaimer

See [LICENSE](LICENSE). This demonstration is provided as-is, without warranty;
route, weather, traffic and cost estimates are not logistics guarantees.
