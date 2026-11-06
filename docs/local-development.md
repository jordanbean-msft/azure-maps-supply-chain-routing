# Local development

Use Python 3.12+, `uv`, Node 22 LTS (22.13+) or 24 LTS, and npm.
Terraform >= 1.9, Azure CLI, azd, and Docker are needed for infrastructure or
container work, not the no-credentials local demo.

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

Open http://localhost:5173. Vite proxies `/api` to http://localhost:8000;
interactive API documentation is at http://localhost:8000/docs.
Use **Load demo** in the UI to create an editable synthetic scenario.

## Modes

`APP_MODE=demo` uses deterministic simulated routes and an in-memory repository.
Restarting the process loses data. The coordinate schematic is not an Azure
road basemap; the UI labels this explicitly.

`APP_MODE=live` requires Azure Maps/Cosmos resources and identity configuration;
see [deployment](deployment.md) and [configuration](configuration-reference.md).
It never silently falls back to simulation. Use only synthetic inputs in the
public demo; identifiers are not a user-authorization system.

## Validation

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/
uv run pytest -W error --cov --cov-report=xml --cov-report=term-missing
uv build
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run typecheck
npm --prefix frontend test
npm --prefix frontend run build
```

Browser tests run the real local API and frontend with simulated upstream data:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

The first Playwright install may require OS libraries; CI installs them with
`--with-deps`. Stop any manually started servers on the test ports before
running browser tests so the test cannot accidentally reuse a live-mode server.

With the API already running, the bounded smoke script creates a seed scenario,
optimizes it, verifies shipment conservation and persisted progress events, and
deletes the scenario:

```bash
bash scripts/smoke-api.sh http://localhost:8000
```

It also accepts a deployed web origin; live mode incurs billable Maps calls.

## Demo walkthrough

1. Load a seed scenario and inspect supplier shipment units and factory capacity.
2. Run optimization; compare allocated routes, ETA, and itemized estimated cost.
3. Select a different road alternative and inspect its geometry/metrics.
4. Add a facility delay or simulated closure and optimize again.
5. Change fuel price or delay penalty to show an economically different ranking.
6. Save changes and reload the scenario while the API process is still running.

In live mode, distinguish reported traffic/weather from assumptions and
simulations. Periodic refreshes consume billable API calls; pause them when not
demonstrating live behavior.

## VS Code and containers

Repository-scoped tasks and debugger configurations are in `.vscode/`.
Open `template-repository.code-workspace` or the repository folder. Task labels
are stable for `preLaunchTask`; Python operations use `uv`.

```bash
docker build -t supply-chain-api .
docker build -t supply-chain-web frontend
```

The API listens on `8000`; non-root Nginx listens on `8080`. Give Nginx an
`API_INTERNAL_URL` reachable from its container, without a trailing slash.
Do not use `localhost` to refer to another container.

Optional hooks:

```bash
uv run pre-commit install --install-hooks
uv run pre-commit install --hook-type pre-push
```
