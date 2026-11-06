# Routing Lab web

React/TypeScript with the Microsoft Azure Maps Web SDK directly managed by React
effects. Native form controls avoid an additional UI dependency. No service keys,
tokens, or scenario contents are written to browser storage; only active scenario
and run identifiers plus their concurrency token are remembered. A remembered run
is restored only when its scenario ETag still matches, preventing old currency or
cost assumptions from being mislabeled after a reload.

## Develop

Use Node 22.13+ or 24 LTS (not Node 23):

```sh
cd frontend
npm ci
npm run dev
npm run lint
npm run typecheck
npm test
npm run build
npm run format:check
```

With an unsupported host Node version, prefix commands with
`npm exec --package=node@22 --`, for example
`npm exec --package=node@22 -- npm test`.

Vite runs on 5173 and proxies `/api` to `http://127.0.0.1:8000`.
`API_PROXY_TARGET` can override the API origin during development.
Start the demo API from the repository root with
`APP_MODE=demo AZURE_ENVIRONMENT=production uv run supply-chain-routing`.

## Browser integration

```sh
npx playwright install --with-deps chromium
npm run test:e2e
```

Playwright auto-starts the real demo API and Vite, exercises seed → edit → save →
optimize → closure → re-optimize → browser reload, and stops its servers afterward.
Run `uv sync --extra dev` in the repository root first. Existing processes are
never reused or stopped; an occupied test port fails explicitly. Override
`E2E_API_PORT` and `E2E_WEB_PORT` to use isolated ports. Reports and failure traces
are ignored in `.gitignore` and `.prettierignore`. `npm run e2e` is an alias.

## Data and interaction guarantees

- Demo mode always labels simulation and provides an SVG coordinate schematic,
  not an invented live basemap. Live map/token errors keep that fallback usable.
  Map attribution is not hidden; traffic overlay is optional and separate from
  route snapshot freshness. Coordinates are also editable with keyboard inputs.
- Save submits the **full** snake_case scenario with `If-Match`. A 412 preserves
  local edits and requires explicit reload. Geocoding resolves candidates only;
  choosing a candidate edits the location and requires Save.
- Optimization uses SSE progress plus persisted run reads, with bounded 2.5-second
  polling as a fallback/watchdog. Sequence/run IDs and timestamps reject obsolete
  results. Requests, streams, SDK maps, and timers clean up on unmount.
- Active saved scenarios refresh/re-optimize every 60 seconds by default (2/5
  minute options and Pause are available). Hidden tabs, dirty forms, active runs,
  and overlapping requests are skipped. This uses existing GET scenario and POST
  optimize APIs; it does not invent a latest-run endpoint. Live re-optimization
  may incur Azure transactions.
- The last successful route snapshot remains visible while editing or after a
  failed/infeasible run, explicitly labeled stale. Allocated costs come from the
  server; unallocated alternatives use clearly labeled browser estimates. Run
  totals sum persisted allocations; hypothetical alternative totals are not
  presented as a re-solved allocation. Traffic time is not counted twice in ETA.
  Alternative estimates use the same eight-part cost formula as the backend:
  driver hours include drive, weather, and simulated delays; one enabled fuel
  override (including zero) replaces the profile price. Route delays are already
  applied by the backend and are not injected twice.
- Public-demo bounds and entity limits are enforced by the API; browser controls
  additionally guide valid targets, quantities, currencies, and US coordinates.
  A closure targets one candidate route, a facility delay targets a location,
  weather severity applies network-wide, and fuel price overrides the assumption.

No Azure provisioning or browser live-account validation is required for demo
mode. Live SDK behavior is covered by a deterministic mock; actual Azure imagery,
token renewal, attribution, and traffic require a configured live account.

## Validation handoff

Validated on Node 22: lint (zero warnings), typecheck (including browser tests),
15 mocked component/integration tests, production build, formatting check, and
Playwright test discovery. The real-backend browser test is intended to run after
the backend worktree is integrated; discovery does not claim that flow passed.
Vite reports its advisory large-chunk warning for the bundled Azure Maps SDK
(approximately 2 MB JavaScript before gzip); the production build succeeds.
