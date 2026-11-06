# Microsoft Entra authentication

The deployed demo uses a **single-tenant SPA/API application registration**.
Terraform owns the registration, service principal, delegated `access_as_user`
scope and web redirect. React uses Microsoft's MSAL authorization-code flow with
PKCE. No client secret, implicit grant or Microsoft Graph permission is needed.

The public static shell loads nonsecret settings from `GET /api/auth/config`.
The workspace mounts only after sign-in. API calls and fetch-based SSE send
bearer tokens in Authorization headers, never URL query strings. FastAPI
validates RS256 signatures using cached tenant signing keys, the exact v2 issuer,
API audience, tenant, lifetime and delegated scope. Health endpoints remain
public for probes; other `/api` endpoints require authentication.

User identity is separate from `AZURE_CLIENT_ID` (workload managed identity),
`AZURE_MAPS_CLIENT_ID` (Maps account) and `MAPS_BROWSER_CLIENT_ID` (render-only
identity). Changing these to the Entra registration ID breaks service access.

## Access and boundaries

Tenant users can sign in subject to tenant consent, Conditional Access and MFA
policies. An administrator may need to approve the delegated scope if user
consent is restricted. Do not weaken tenant policies or add broad Graph
permissions to bypass that approval.

Users retain this demo's shared scenario semantics. Any signed-in tenant user
with a scenario ID can access it; scenario enumeration remains disabled.
Per-user ownership, organizational roles and production audit controls are
not implemented. Use synthetic data only. The scheduled job operates directly
through its managed identity, not an interactive user token.

## Local development

`.env.example` explicitly uses `AUTH_ENABLED=false` for deterministic, offline
demonstrations. To test real Entra sign-in locally, register the exact Vite SPA
redirect, for example `http://localhost:5173/`, in Terraform's authentication
redirect configuration. Set these backend values from provisioning outputs:

```dotenv
AUTH_ENABLED=true
ENTRA_TENANT_ID=<tenant-uuid>
ENTRA_CLIENT_ID=<registration-client-uuid>
ENTRA_API_SCOPE=<full-access_as_user-scope-uri>
```

Keep `APP_MODE=demo` if live Maps/Cosmos are not needed. No frontend secret or
build-time token is required. Redirects use the current web origin plus `/`;
`localhost` and `127.0.0.1` are different origins. Production redirects must use
HTTPS. Sign-out unmounts the workspace and invokes Entra logout.

## Verification

```sh
bash scripts/smoke-auth.sh https://<web-host>
```

This verifies the static shell, readiness, enabled auth discovery and rejection
of anonymous/invalid/spoofed user credentials on protected API routes.
It does **not** claim a successful interactive login or route optimization.
CI OIDC identities are app-only and cannot impersonate a signed-in user.

For the full bounded scenario smoke, obtain a valid delegated access token
through an approved interactive flow. Save only the raw token in a private file
(`chmod 600`), without logging it or committing it, then run:

```sh
SMOKE_ACCESS_TOKEN_FILE=/private/path/token \
  bash scripts/smoke-api.sh https://<web-host>
```

The script sends the token through a temporary private header file, not a curl
command-line argument, and removes that file on exit. Remove the supplied token
file after use. Never disable JWT verification for smoke tests.

References:
[MSAL browser](https://learn.microsoft.com/entra/msal/javascript/browser/),
[SPA authorization code](https://learn.microsoft.com/entra/identity-platform/v2-oauth2-auth-code-flow),
[API access-token validation](https://learn.microsoft.com/entra/identity-platform/access-tokens#validate-tokens).
