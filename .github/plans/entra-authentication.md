# Entra authentication and deployment

The React application uses MSAL with PKCE. The API validates single-tenant
delegated tokens; Azure workload identities remain independent of user identity.
All signed-in tenant users share the bounded demo scenarios, as before.

- [x] Inspect deployment context and define shared authentication contract.
- [ ] Backend (auth-api worktree): `src/`, Python manifests/lock and Python tests.
  Add `GET /api/auth/config` returning `enabled`, `tenant_id`, `client_id`, `scope`.
  Protect other `/api` endpoints when `AUTH_ENABLED=true`; health stays public.
  Settings: `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_API_SCOPE`.
  Validate RS256 signature, v2 issuer/audience/tenant/time and delegated scope.
  Acceptance: focused token and API tests, Ruff, mypy, warning-free tests.
- [ ] Frontend (auth-web worktree): `frontend/` only.
  Read discovery before mounting the workspace; MSAL login/logout; bearer tokens
  on every API and streamed SSE call, never URL tokens. Local disabled auth stays
  compatible. Acceptance: auth and stream tests, frontend lint/types/tests/build.
- [ ] Infrastructure (auth-infra worktree): `infra/` only.
  Create secretless single-tenant SPA/API registration, service principal, User
  `access_as_user` delegated scope and v2 tokens. Configure production redirect
  without a graph dependency cycle; set API auth environment settings and export
  nonsecret IDs/scope. Preserve internal API and existing managed identities.
  Acceptance: format/init/validate, mocked plans, TFLint and deployment plan.
- [ ] Integration (main worktree): documentation, deployment scripts/workflows,
  environment examples and VS Code automation if commands change. Review worktree
  commits and integrate; run combined checks and local browser walkthrough.
- [ ] Azure (main worktree; depends on all implementation/validation):
  establish dedicated azd/state context, validate quotas/policy, provision with
  azd (including registration), deploy both services and verify anonymous API
  rejection, discovery, readiness and actual deployed sign-in redirect behavior.
  Record any interactive sign-in verification limitation explicitly.
