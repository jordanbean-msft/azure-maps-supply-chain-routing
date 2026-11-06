# Microsoft Entra authentication

The deployed demo uses a **single-tenant SPA/API application registration**.
Terraform owns the registration, service principal, delegated `access_as_user`
scope and web redirect. React uses Microsoft's MSAL authorization-code flow with
PKCE. No client secret or implicit grant is used. Terraform records only the
delegated Microsoft Graph `User.Read` permission for the user's own profile;
it creates no application permissions, admin consent grants or preauthorization.

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

## Account header and optional profile consent

The same Fluent header labels offline mode as `Demo workspace`. Signed-in users
see `Howdy First Last!` using Graph `givenName` and `surname`, with ID-token
`given_name`/`family_name` or display name as a fallback. Names are never invented.
The Fluent avatar displays the actual Microsoft photo when available, otherwise
initials. A missing photo (HTTP 404) is normal.

Sign-in requests the API scope in `scopes` and Graph
`https://graph.microsoft.com/User.Read` in `extraScopesToConsent`. MSAL supports
consent for another resource without mixing resource scopes in the API token.
Profile loading separately acquires a Graph-only access token and calls
`/v1.0/me?$select=givenName,surname,displayName` and `/v1.0/me/photo/$value`.
The routing API token provider continues to request only `access_as_user`.

Existing sessions without Graph consent remain usable. Profile/token failures
never block the workspace or automatically launch interactive authentication.
The explicit **Load profile photo** action opens an MSAL consent popup. Tenant
policy may require administrator approval; this application does not grant it.
Denied consent and other Graph failures retain the ID-token/initials fallback.
Fetched names, photos and Graph tokens are kept in memory only, not logged or
persisted. Profile token requests disable MSAL token caching with `storeInCache`;
the API sign-in session retains its existing session-storage cache, never
localStorage, and is cleared on logout.
Profile requests are aborted and photo object URLs revoked when the account
header unmounts, including session expiry and logout.

Offline permission regression checks:

```sh
terraform -chdir=infra test -filter=tests/entra.tftest.hcl -filter=tests/workload-auth.tftest.hcl
bash infra/tests/entra-permissions.test.sh
```

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
[MSAL multi-resource consent](https://learn.microsoft.com/entra/msal/javascript/browser/resources-and-scopes#consent),
[Graph own profile](https://learn.microsoft.com/graph/api/user-get),
[Graph profile photo](https://learn.microsoft.com/graph/api/profilephoto-get),
[SPA authorization code](https://learn.microsoft.com/entra/identity-platform/v2-oauth2-auth-code-flow),
[API access-token validation](https://learn.microsoft.com/entra/identity-platform/access-tokens#validate-tokens).
