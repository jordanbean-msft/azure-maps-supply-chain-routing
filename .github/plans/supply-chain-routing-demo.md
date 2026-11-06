# Supply chain routing demo

Approved scope and source: session `a951a2e4-af67-411c-bb1a-0724e0d90e82/plan.md`.
API, frontend, and infrastructure changes were implemented in isolated worktrees
and integrated on main. Application images now build remotely in ACR and run in
Azure with Entra authentication. The current deployment record is
`.github/plans/entra-authentication.md`; authenticated cloud route acceptance
still requires an interactive tenant user.
Preserve `template_repository`
and the `template-repository` CLI alias to avoid breaking existing imports,
tests, CI and consumers; the project/display name is `supply-chain-routing`.

## Original todos

- [x] **1. project-foundation — Establish project structure and contracts.**
  Owner: foundation writer. Files: `src/template_repository/models/`, config,
  runtime, `frontend/`, Dockerfiles, `azure.yaml`, `.env.example`, `.vscode/`.
  Acceptance: typed snake_case contracts, no-credentials demo configuration,
  health/config endpoints, frontend API request, buildable scaffolds, common tasks.
  Validate: Ruff check/format, mypy, pytest `-W error`, frontend lint/typecheck/test/build/format.
- [x] **2. cosmos-persistence — Implement domain models and Cosmos persistence.**
  Backend owner; depends on 1. Extend shared models, add async repository interfaces,
  Cosmos CRUD, ETags, TTL and seed data. Verify fake-repository concurrency and
  scenario-scoped partition keys. Implemented; fake Cosmos CRUD/ETag/TTL and
  memory expiration tests pass without cloud credentials.
- [x] **3. azure-maps-integration — Implement Azure Maps integration.**
  Backend owner; depends on 1 and persistence contracts from 2. Add async geocode,
  matrix, directions, traffic/weather and token services behind DI. Test retries,
  throttling, missing routes and partial failures. Implemented with stable
  v2025 routing and Weather Along Route 1.1; actual road geometry, ETA offsets,
  forecast-horizon warnings, and current/future departure handling are tested.
  Live Maps identity assignments are verified; route/traffic/weather calls await
  authenticated cloud functional acceptance.
- [x] **4. optimization-engine — Implement cost and optimization engine.**
  Backend owner; depends on 1. Add transparent costs, min-cost-flow allocation and
  alternatives. Test infeasibility, capacity, prohibited lanes and deterministic
  rankings. OR-Tools exception: no equivalent Microsoft constrained optimizer.
  Implemented; capacity, closures, numerical bounds, precision, and costs pass
  deterministic tests.
- [x] **5. fastapi-workflows — Implement FastAPI application workflows.**
  Backend owner; depends on 2, 3, 4. Implement session API contract, persisted
  asynchronous progress/SSE, problem details, bounded inputs and idempotency.
  Validated with async fake-service tests plus a real local API smoke:
  seed, optimize, shipment conservation, persisted SSE events, ETag deletion.
  Configured live initialization failures abort startup for ACA recovery.
- [x] **6. react-experience — Build the interactive React application.**
  Frontend owner; depends on 1 and API integration from 5. Own `frontend/` except
  coordinate shared `types.ts` changes with backend. Add editor, map, allocation
  and disruption comparison; verify component tests and seed-to-optimization flow.
  Implemented and integrated. Fifteen component tests and a real Chromium
  seed/edit/optimize/closure/comparison/reload flow pass. Real-browser validation
  found and fixed Vite/Nginx Host preservation without weakening origin checks.
- [x] **7. azure-infrastructure — Implement Azure deployment resources.**
  Infrastructure owner; depends on 1 and stable runtime requirements. Own `infra/`,
  later azd integration and refresh job. Foundation supplies Dockerfiles only.
  Use pre-created resource group, managed identity, internal API ingress, web
  public ingress. Validate Terraform fmt/init/validate with zero warnings.
  Implemented. Terraform init/fmt/validate (zero warnings), five mocked plans,
  TFLint and image synchronization hook tests pass. Azure provisioning and remote
  image builds are now verified; see the authentication deployment record.
- [x] **8. observability-resilience — Add observability, resilience, and cost controls.**
  Integration owner; depends on 3, 5, 7. Add telemetry, request correlation,
  quotas, cache/TTL, health dependency checks and alerts. Verify actionable failure
  telemetry and transaction limits. Structured logging, correlation, Azure
  Monitor instrumentation, service diagnostics, bounds, caching, TTL, and
  failure/readiness tests are integrated. Live API startup confirms successful
  Azure Monitor telemetry export and managed-identity Cosmos initialization.
- [ ] **9. delivery-documentation — Complete deployment validation.**
  Integration owner; depends on all preceding work. Expand CI, OIDC deployment,
  architecture/setup/demo documentation and deployed smoke tests. CI jobs, OIDC workflows,
  architecture/research/operations/configuration docs, VS Code tasks/debuggers,
  and the bounded local/deployed API smoke script are implemented and checked.
  Local browser E2E passes. ACR remote builds resolve the local daemon TLS blocker
  without disabling certificate validation. Provisioning, healthy app revisions,
  the live authentication-boundary smoke, Chromium sign-in entry and a cloud
  refresh execution now pass. Remaining acceptance is the signed-in cloud
  seed/optimize/compare workflow, requiring a real delegated user session.
  GitHub CI has not been triggered or claimed green remotely.

## Contract decisions

- JSON and Cosmos partition key use `snake_case`; use `/scenario_id`, not the
  original planning sketch's `/scenarioId`. Scenario document `scenario_id = id`.
- Python contracts: `src/template_repository/models/`; matching TypeScript:
  `frontend/src/types.ts`. API route IDs also use snake_case in OpenAPI.
- Runtime defaults: `APP_MODE=demo`, in-memory persistence and explicitly simulated
  routes; live mode must never silently downgrade an Azure failure to simulation.
- `GET /api/config` advertises availability; `GET /api/maps/token` returns
  `{token, client_id, expires_on}` only in configured live mode (503 otherwise).
- Container contract: API `8000`, non-root web `8080`, web reverse-proxies `/api/`
  and `/health` to `API_INTERNAL_URL` and disables buffering for SSE.
- Backend handoff API contract is in the session `files/api-contract.md`.

## Original validation status (historical)

- Passed: Ruff lint/format, mypy (45 source files), **109 warning-free Python
  tests, 93.56% coverage**, wheel/source packaging.
- Passed on Node 22.23.4: frontend lint, format, types, **15 component tests**,
  production build, and **one real Chromium E2E test**. The build reports the
  Azure Maps SDK bundle-size advisory (about 538 KB gzip); it is not suppressed.
- Passed: standalone local API smoke (12 candidate routes, four allocations,
  persisted progress); temporary API and browser test servers stopped.
- Passed: non-root Nginx runtime (UID 101), configuration validation, web health,
  and compiled index serving using prebuilt local assets. This is not a full
  Dockerfile build; the host emitted AIO compatibility notices.
- Passed: Terraform init/fmt/validate with zero errors/warnings, five mock plans,
  recursive TFLint, three hook tests; workflow YAML and actionlint.
- Blocked: full API/web Dockerfile builds, because daemon-side HTTPS requests to
  package registries fail TLS handshakes. Native TLS did not fix the Python
  failure; npm registry ping independently reproduces the daemon network issue.
- Deferred: real Azure provisioning/deployment, live map/Cosmos/weather/RBAC/DNS
  verification, scheduled cloud refresh, and deployed smoke. No push performed.
- Browser dependencies were extracted into session-local storage after the host
  lacked NSS/NSPR and sudo installation was unavailable; shared OS packages were
  not changed. All temporary task containers and servers were stopped.
