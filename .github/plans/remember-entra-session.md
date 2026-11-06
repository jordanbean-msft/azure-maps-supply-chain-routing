# Remember the Entra sign-in

Use Microsoft's supported SPA session cache and Entra SSO cookie rather than
placing passwords or raw tokens into application cookies. Keep authorization
code/PKCE, API bearer validation, scopes and registration unchanged.

- [x] Session restoration (`frontend/src/AuthGate.tsx`, `main.tsx`):
  use MSAL localStorage for shared tab/session caching; attempt cookie-backed
  silent SSO once when no cached account exists. Never start automatic
  interactive redirects or choose arbitrarily between multiple cached accounts.
  Keep the existing root redirect but do not bootstrap the app in a silent
  authentication iframe. Honor explicit sign-out on reload and across tabs.
  Document that browser/privacy/tenant policy can still require interaction.
  Complete: shared MSAL cache plus one silent SSO attempt, explicit fallback,
  active/single-account restoration, persistent nonsecret logout preference and
  cross-tab lock. The callback iframe does not mount AuthGate or the workspace.
- [x] Tests/docs (depends on session restoration): cover cached and silent
  return visits, interaction-required/blocked-cookie fallback, ambiguous accounts,
  aborted restoration, explicit sign-out, cross-tab sign-out and iframe behavior.
  Use synthetic accounts/tokens only. Run frontend lint/format/types/tests/build
  and real Chromium session/normal workflow checks. Update authentication docs,
  including MSAL-managed cookie/cache behavior and Keep me signed in caveats.
  Complete: 71 React tests, ESLint, Prettier, TypeScript and production build
  pass. Three Chromium workflows pass; the new synthetic-MSAL workflow verifies
  reload/new-tab cache reuse, cookie-only restoration in a fresh browser context,
  empty callback iframe, immediate cross-tab logout and suppressed automatic
  restoration after logout. No real personal Entra cookie/token was accessed.
- [x] Rollout (depends on tests/docs): complete the current Azure validation
  workflow, deploy web only with secure ACR, verify exact assets, healthy ready
  revision and auth boundary. Preserve API images, all roles and registration.
  Record that real personal Entra-session persistence requires user acceptance.
  Complete: authoritative Azure validation and all ten Terraform preflight
  checks pass. Provision only reconciled eight diagnostic settings; verified
  AcrPull before secure ACR web-only deployment. Revision
  `ca-njk0ztnkmgrmn-web--azd-1794008368` is healthy/running and latest ready.
  Exact deployed JS/CSS comparison and live auth smoke pass after revision
  activation. API/refresh images, roles, registration and all authorized tags
  are unchanged. Actual personal SSO remains interactive user acceptance.
