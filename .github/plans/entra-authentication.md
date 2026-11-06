# Entra authentication and deployment

The React application uses MSAL with PKCE. The API validates single-tenant
delegated tokens; Azure workload identities remain independent of user identity.
All signed-in tenant users share the bounded demo scenarios, as before.

- [x] Inspect deployment context and define shared authentication contract.
- [x] Backend (auth-api worktree): `src/`, Python manifests/lock and Python tests.
  Completed on `copilot/entra-api`: focused auth/config tests (75), full warning-free
  suite (180), Ruff format/check and mypy passed with frozen dependencies.
  Add `GET /api/auth/config` returning `enabled`, `tenant_id`, `client_id`, `scope`.
  Protect other `/api` endpoints when `AUTH_ENABLED=true`; health stays public.
  Settings: `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_API_SCOPE`.
  Validate RS256 signature, v2 issuer/audience/tenant/time and delegated scope.
  Acceptance: focused token and API tests, Ruff, mypy, warning-free tests.
- [x] Frontend (auth-web worktree): `frontend/` only.
  Read discovery before mounting the workspace; MSAL login/logout; bearer tokens
  on every API and streamed SSE call, never URL tokens. Local disabled auth stays
  compatible. Acceptance: auth and stream tests, frontend lint/types/tests/build.
- [x] Infrastructure (auth-infra worktree): `infra/` only.
  Create secretless single-tenant SPA/API registration, service principal, User
  `access_as_user` delegated scope and v2 tokens. Configure production redirect
  without a graph dependency cycle; set API auth environment settings and export
  nonsecret IDs/scope. Preserve internal API and existing managed identities.
  Acceptance: format/init/validate, mocked plans, TFLint and deployment plan.
  Validated: AzureAD 3.10.0 locked for Linux ARM64/AMD64; format/init/validate
  and recursive TFLint pass without warnings; 10 mocked registration, workload
  and deployment plans pass. Production SPA root also supports MSAL post-logout;
  extra redirects are explicit only. Refresh keeps its non-HTTP entry point and
  receives the same nonsecret settings for centralized configuration validation.
  No live plan/apply or Azure resource changes performed in this worktree.
- [ ] Integration (main worktree): documentation, deployment scripts/workflows,
  environment examples and VS Code automation if commands change. Review worktree
  commits and integrate; run combined checks and local browser walkthrough.
- [ ] Azure (main worktree; depends on all implementation/validation):
  establish dedicated azd/state context, validate quotas/policy, provision with
  azd (including registration), deploy both services and verify anonymous API
  rejection, discovery, readiness and actual deployed sign-in redirect behavior.
  Record any interactive sign-in verification limitation explicitly.
