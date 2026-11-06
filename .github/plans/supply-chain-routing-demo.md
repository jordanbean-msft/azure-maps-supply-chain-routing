# Supply chain routing demo

Approved scope and source: session `a951a2e4-af67-411c-bb1a-0724e0d90e82/plan.md`.
Only the foundation is implemented in this change. Preserve `template_repository`
and the `template-repository` CLI alias to avoid breaking existing imports,
tests, CI and consumers; the project/display name is `supply-chain-routing`.

## Original todos

- [x] **1. project-foundation — Establish project structure and contracts.**
  Owner: foundation writer. Files: `src/template_repository/models/`, config,
  runtime, `frontend/`, Dockerfiles, `azure.yaml`, `.env.example`, `.vscode/`.
  Acceptance: typed snake_case contracts, no-credentials demo configuration,
  health/config endpoints, frontend API request, buildable scaffolds, common tasks.
  Validate: Ruff check/format, mypy, pytest `-W error`, frontend lint/typecheck/test/build/format.
- [ ] **2. domain-persistence — Implement domain models and Cosmos persistence.**
  Backend owner; depends on 1. Extend shared models, add async repository interfaces,
  Cosmos CRUD, ETags, TTL and seed data. Verify fake-repository concurrency and
  scenario-scoped partition keys. No implementation yet.
- [ ] **3. azure-maps — Implement Azure Maps integration.**
  Backend owner; depends on 1 and persistence contracts from 2. Add async geocode,
  matrix, directions, traffic/weather and token services behind DI. Test retries,
  throttling, missing routes and partial failures. No implementation yet.
- [ ] **4. optimization — Implement cost and optimization engine.**
  Backend owner; depends on 1. Add transparent costs, min-cost-flow allocation and
  alternatives. Test infeasibility, capacity, prohibited lanes and deterministic
  rankings. OR-Tools exception: no equivalent Microsoft constrained optimizer.
  No implementation yet.
- [ ] **5. api-workflows — Implement FastAPI application workflows.**
  Backend owner; depends on 2, 3, 4. Implement session API contract, persisted
  asynchronous progress/SSE, problem details, bounded inputs and idempotency.
  Validate async API tests with fake Azure services. No implementation yet.
- [ ] **6. interactive-frontend — Build the interactive React application.**
  Frontend owner; depends on 1 and API integration from 5. Own `frontend/` except
  coordinate shared `types.ts` changes with backend. Add editor, map, allocation
  and disruption comparison; verify component tests and seed-to-optimization flow.
  No implementation yet.
- [ ] **7. azure-infrastructure — Containerize and provision Azure resources.**
  Infrastructure owner; depends on 1 and stable runtime requirements. Own `infra/`,
  later azd integration and refresh job. Foundation supplies Dockerfiles only.
  Use pre-created resource group, managed identity, internal API ingress, web
  public ingress. Validate Terraform fmt/init/validate with zero warnings.
  No infrastructure implemented or provisioned yet.
- [ ] **8. observability — Add observability, resilience, and cost controls.**
  Integration owner; depends on 3, 5, 7. Add telemetry, request correlation,
  quotas, cache/TTL, health dependency checks and alerts. Verify actionable failure
  telemetry and transaction limits. No implementation yet.
- [ ] **9. delivery-validation — Update CI/CD, documentation, and demo validation.**
  Integration owner; depends on all preceding work. Expand CI, OIDC deployment,
  architecture/setup/demo documentation and deployed smoke tests. Full CI/container
  and end-to-end verification is deferred, not claimed by foundation.

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

## Validation status

- Passed: `uv sync --extra dev`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy src/`,
  `uv run pytest -W error` (26 tests), warning-free coverage (70.47%), `uv build`.
- Passed on Node 22.23.4: npm install/lock generation, lint, typecheck,
  test (3 tests), production build and format check. Lockfiles use public npm/PyPI
  registries. The host's default Node 23 is unsupported by upstream tools; use
  Node 22 LTS (22.13+) or 24 LTS as documented.
- Passed local smoke: API `/health/ready`, Vite index and Vite `/api/config`
  reverse-proxy response. Smoke servers stopped after verification.
- Blocked/deferred: Docker runtime/build checks; Docker Desktop daemon is not
  available (named pipe connection failure; WSL Docker link is broken).
  Dockerfiles and Nginx are scaffolds, not claimed container-runtime verified.
- Terraform unchanged; infrastructure validation, Azure provisioning/deployment
  and full application integration are explicitly excluded.
