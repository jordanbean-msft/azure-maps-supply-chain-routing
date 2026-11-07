# Selected-route direction deployment

Status: Deployed

## Current scope

Modify the existing Terraform/azd `demo` environment in East US 2,
subscription `0ec6c427-01d3-4462-ae56-fd9656157157`, `rg-scroute-eus2`.
Autopilot continues the existing demo update. Animate only the inspected route
from supplier to factory, label start/destination, and provide static direction
cues for reduced-motion preferences. Support both Azure Maps and the schematic.
Keep allocation colors/semantics, map interaction and viewport unchanged.

Deploy web only via secure ACR. No new dependencies, resources, permissions,
capacity or commands. Preserve SSO, backend/refresh images, registration, data,
roles and authorized exception tags.

## Current preparation checklist

- [x] Inspect existing map layers, route geometry and browser coverage.
- [x] Implement selected-route direction and reduced-motion behavior.
- [x] Verify focused map regressions, frontend checks and browser animation.
- [x] Complete current Azure validation and record proof.
- [x] Reconcile reviewed non-destructive infrastructure and verify AcrPull.
- [x] Deploy web only; verify ready revision, exact assets and auth smoke.

## Functional verification

The selected route has a six-second repeating supplier-to-factory arrow,
START/END labels and endpoint emphasis in both map modes. Azure Maps uses its
SDK distance/path utilities and a stable HTML marker, oriented with projected
screen coordinates so rotation/pitch are honored. The schematic uses a native
CSS SVG motion path. No frame-driven React rendering, new source or map rebuild.

An animation checkbox permits static direction; OS reduced-motion changes are
honored immediately. Only the inspected route moves. Deselecting/changing routes
or unmounting cancels the prior frame loop; hidden tabs skip frame updates.
The banner explicitly distinguishes direction illustration from vehicle tracking.

Final ESLint, Prettier, 73 React tests, TypeScript and production build pass.
Four Chromium workflows pass, including actual rendered arrow positions at
the start/end, pause/resume, reduced-motion changes and long-text containment
at six widths. SDK mock tests cover movement, projection, selection changes,
cleanup, static direction and stable sources/camera. Desktop/mobile screenshots
inspected. No real personal authenticated cloud-map session is claimed.
Established commands/entrypoints and VS Code automation are unchanged.

## 7. Validation Proof

Current evidence recorded: 2026-11-06T18:04:44-06:00.

The current azure-validate workflow ran the existing Terraform/azd recipe.
AZD installation, authentication, selected `demo` environment, subscription/
tenant/location and official azure.yaml schema validation pass.
`azd provision --preview --no-prompt` succeeds; real plan JSON inspection
asserts exactly eight in-place diagnostic-setting updates, zero additions/
destruction and no other resource changes. Current preview is saved in session
`files/route-direction-preview.log`.

The complete `validate-terraform.sh infra` preflight passes all ten checks using
azd-generated `demo.conf.json` and `main.tfvars.json`. Authenticated remote-state
access, format/validate, real plan, state list and template/JSON checks have zero
errors/warnings. Generated `infra/tfplan` removed. `azd package --all --no-prompt`
passes in secure remote-build mode; Docker contexts/non-root users and checked-in
lockfiles remain unchanged.

ESLint, Prettier, 73 React tests, TypeScript and production build pass. Four
Chromium workflows pass, including actual supplier-to-factory animation geometry,
reduced-motion/pause, normal routing/profile/SSO and six-width text containment.
Screenshots inspected; only the existing Maps bundle-size advisory remains.
No new command or entrypoint requires a VS Code automation change.

All 14 application ARM resources retain the authorized exception tag. The 97
inherited policy assignments retrieved earlier this session remain applicable;
no infrastructure source or policy setting changed. Static role review and
the no-change plan confirm unchanged registry AcrPull/AcrPush, Maps-account
workload Data Reader, scenario-container native Cosmos Data Contributor,
and browser render/traffic reads only. Animation uses no additional data API,
capacity or permission.

## All validation checks pass

- [x] AZD installation, selected environment, authentication, subscription/location.
- [x] Official azure.yaml schema validation.
- [x] Aspire pre/post-provisioning checks not applicable.
- [x] Non-destructive real provision preview.
- [x] Frontend build and functional verification.
- [x] Existing Docker contexts, non-root users and checked-in lockfiles unchanged.
- [x] Secure remote-build mode package validation.
- [x] Complete Terraform preflight including authenticated state and real plan.
- [x] Existing policy/tag preservation and static data-plane role verification.

## Selected-route direction rollout result

Verified: 2026-11-06T18:09:19-06:00.

Web update deployed:
https://ca-njk0ztnkmgrmn-web.icyflower-2a21f8a0.eastus2.azurecontainerapps.io/

`azd provision --no-prompt` completed the reviewed eight in-place diagnostic
reconciliations with no additions/destruction. Registry-scoped AcrPull was
confirmed for all three workloads before successful secure ACR
`azd deploy web --no-prompt`. `azd show` confirms the expected endpoints.

Revision `ca-njk0ztnkmgrmn-web--azd-1794010096` equals latest ready and is
healthy/running. Image:
`crnjk0ztnkmgrmn.azurecr.io/supply-chain-routing/web-demo:azd-deploy-1794009965`.
After waiting for activation, deployed `index-CUSBZMkw.js` and
`index-BDe50HX1.css` match the validated build byte-for-byte. Live auth smoke
passes: discovery/readiness available; anonymous, invalid and spoofed
credentials rejected.

API revision remains `ca-njk0ztnkmgrmn-api--azd-1794006389`, latest equals ready;
API/refresh keep `api-demo:azd-deploy-1794006304`.
Live role verification confirms unchanged Maps-account workload Data Reader,
browser render/traffic role, and scenario-container native Cosmos Data
Contributor for API/refresh. All 14 application ARM resources retain the
authorized tag. SSO, registration, data, backend and scopes are unchanged.

73 unit tests, frontend checks/build and four local Chromium workflows pass.
The real schematic animation is measured from source to destination; SDK
movement/projection/cleanup is tested with deterministic mocks. Reduced-motion,
manual static mode, stable camera and six-width text containment are verified.
Screenshots inspected. Personal authenticated live-map visual acceptance is
not claimed by deterministic browser fixtures.

## Previous text containment deployment (historical)

Previous status: Deployed

## Current scope

Modify the existing Terraform/azd `demo` environment in East US 2,
subscription `0ec6c427-01d3-4462-ae56-fd9656157157`, `rg-scroute-eus2`.
Autopilot continues the existing demo update. Deploy web only using secure ACR
remote build. Fix text wrapping, flexible panel/control sizing, warning bullet
indentation and bounded schematic facility labels; retain complete text and
working map selection. Preserve the intentionally scrollable route table.

No new resources, capacity, dependencies, commands, redirects or permissions.
Keep SSO, registration, API/refresh images, Cosmos data, all roles and the
authorized exception tags unchanged. Existing VS Code automation remains valid.

## Current preparation checklist

- [x] Reproduce long-name/warning overflow in Chromium before fixing.
- [x] Fix responsive sizing, badge wrapping, bullet gutter and map labels.
- [x] Verify frontend lint/format/types/build, 71 tests and four browser flows.
- [x] Inspect desktop, narrow two-column and mobile screenshots.
- [x] Complete current Azure validation and record proof.
- [x] Reconcile reviewed non-destructive infrastructure and verify AcrPull.
- [x] Deploy web only; verify ready revision, exact assets and auth smoke.

## Functional verification

The new browser regression measures rendered text bounds in panels, headings,
badges, summaries, warnings, legends, disruption controls and the schematic.
It verifies bullet inset and no horizontal page overflow with long names and
unbroken upstream references at 1440, 1024, 768, 701, 390 and 320px widths.
All four Chromium workflows pass, including the unchanged authenticated-session,
profile and full local shipment/disruption workflows. Schematic labels wrap and
edge-align without losing text; whole-facility hit targets remain selectable.
The earlier browser failure exposed and verified that related hit-target fix.
Final ESLint, Prettier, 71 React tests, TypeScript and build pass. A generated
failed-trace HTML report was removed before final lint to avoid linting bundled
third-party report JavaScript. No Python or Terraform source changed.

## 7. Validation Proof

Current evidence recorded: 2026-11-06T17:50:51-06:00.

The current azure-validate workflow ran the existing Terraform/azd recipe.
AZD installation, authentication, selected `demo` environment, subscription/
tenant/location and official azure.yaml schema validation pass.
`azd provision --preview --no-prompt` succeeds; inspection of the real plan JSON
asserts exactly eight in-place diagnostic-setting updates, zero additions/
destruction and no other resource changes. Current preview is saved in session
`files/text-containment-preview.log`.

The complete `validate-terraform.sh infra` preflight passes all ten checks using
azd-generated `demo.conf.json` and `main.tfvars.json`. Authenticated remote-state
access, format/validate, real plan, state list and template/JSON checks have zero
errors/warnings. Generated `infra/tfplan` removed. `azd package --all --no-prompt`
passes in secure remote-build mode; Docker contexts/non-root users and checked-in
lockfiles remain unchanged.

ESLint, Prettier, 71 React tests, TypeScript and production build pass. Four
Chromium workflows pass, including rendered text geometry and warning bullet
gutter checks at six widths, plus normal routing, profile and remembered SSO.
Desktop/mobile screenshots inspected; the existing Maps bundle advisory remains.
No new command or entrypoint requires a VS Code automation change.

All 14 application ARM resources retain the authorized exception tag. The 97
inherited policy assignments retrieved earlier this session remain applicable;
no infrastructure source or policy setting changed. Static role review and
the no-change plan confirm unchanged registry AcrPull/AcrPush, Maps-account
Data Reader for workloads, scenario-container native Cosmos Data Contributor,
and browser render/traffic reads only. No added capacity or role is requested.

## All validation checks pass

- [x] AZD installation, selected environment, authentication, subscription/location.
- [x] Official azure.yaml schema validation.
- [x] Aspire pre/post-provisioning checks not applicable.
- [x] Non-destructive real provision preview.
- [x] Frontend build and functional verification.
- [x] Existing Docker contexts, non-root users and checked-in lockfiles unchanged.
- [x] Secure remote-build mode package validation.
- [x] Complete Terraform preflight including authenticated state and real plan.
- [x] Existing policy/tag preservation and static data-plane role verification.

## Text-containment rollout result

Verified: 2026-11-06T17:55:57-06:00.

Web update deployed:
https://ca-njk0ztnkmgrmn-web.icyflower-2a21f8a0.eastus2.azurecontainerapps.io/

`azd provision --no-prompt` completed the reviewed eight in-place diagnostic
reconciliations with no additions/destruction. Registry-scoped AcrPull was
confirmed for all three workloads before the successful secure ACR
`azd deploy web --no-prompt`. `azd show` confirms the expected endpoints.

Revision `ca-njk0ztnkmgrmn-web--azd-1794009292` equals latest ready and is
healthy/running. Image:
`crnjk0ztnkmgrmn.azurecr.io/supply-chain-routing/web-demo:azd-deploy-1794009151`.
After waiting for activation, deployed `index-2FrvDquD.js` and
`index-ByXiMwOi.css` match the validated build byte-for-byte. Live auth smoke
passes: discovery/readiness available; anonymous, invalid and spoofed
credentials rejected.

API revision remains `ca-njk0ztnkmgrmn-api--azd-1794006389`, latest equals ready;
API/refresh keep `api-demo:azd-deploy-1794006304`.
Live role verification confirms unchanged Maps-account workload Data Reader,
browser render/traffic role, and scenario-container native Cosmos Data
Contributor for API/refresh. All 14 application ARM resources retain the
authorized tag. SSO, registration, data, backend and scopes are unchanged.

71 unit tests, frontend checks/build and four local Chromium workflows pass;
the six-width regression checks actual rendered text bounds and bullet inset
with long content. Screenshots inspected. Personal authenticated live-map visual
acceptance remains separate from deterministic browser coverage.

## Previous remembered Entra session deployment (historical)

Previous status: Deployed

## Current scope

Update the existing Terraform/azd `demo` environment, subscription
`0ec6c427-01d3-4462-ae56-fd9656157157`, East US 2, `rg-scroute-eus2`.
Deploy web only via secure ACR remote build. Use MSAL-managed localStorage and
Microsoft Entra's SSO cookie to restore returning sessions, with a single silent
attempt and explicit sign-in fallback. Honor logout across reloads/tabs and
avoid recursive app startup in silent-auth callback iframes.

Do not store passwords/raw tokens in application cookies, change authentication
flows/scopes, grant permissions, create secrets, or weaken MFA/Conditional Access.
No new resources, dependencies, redirects or capacity. Keep API/refresh images,
registration, browser Maps role and the authorized exception tags unchanged.
Autopilot continues the existing demo update in the same Azure environment.

## Current preparation checklist

- [x] Inspect authentication/cache, callback bootstrap and current tests.
- [x] Research official Microsoft MSAL cache and SSO documentation.
- [x] Implement and verify remembered session, fallback and logout behavior.
- [x] Run current azure-validate workflow and record proof.
- [x] Preview/reconcile existing infrastructure, then confirm AcrPull.
- [x] Deploy web only and verify ready revision, exact assets and auth smoke.

## Functional verification

71 React tests, frontend ESLint/Prettier, TypeScript and production build pass.
Three real Chromium workflows pass against the unchanged deterministic local
API. Synthetic Microsoft session coverage verifies local-cache reload/new-tab
reuse, cookie-only restoration in a fresh context, no application bootstrap in
callback iframes, explicit cross-tab logout and no silent reauthentication after
logout. Normal shipment/disruption/profile workflows remain passing.
No actual user's Entra session or cookie has been inspected; browser/tenant
restrictions may still require interaction. The established commands/entrypoint
remain valid, so no VS Code automation change is needed.

## 7. Validation Proof

Current evidence recorded: 2026-11-06T17:34:49-06:00.

The current azure-validate workflow uses the existing Terraform/azd recipe.
AZD installation, selected `demo` environment, authentication, subscription,
tenant, location and official azure.yaml schema validation pass.
`azd provision --preview --no-prompt` succeeds: zero additions, eight in-place
diagnostic-destination drift reconciliations, zero destruction. No image,
registration, role, network or identity change is proposed. Current preview:
session `files/sso-provision-preview.log`.

The complete `validate-terraform.sh infra` preflight passes all ten checks using
the azd-generated `demo.conf.json` backend and `main.tfvars.json`. Authenticated
state access, format/validate, real plan, state list and template/JSON checks
pass with no errors or warnings. The temporary `infra/tfplan` was removed.
`azd package --all --no-prompt` passes with secure remote ACR builds selected.
Frontend lint/format, 71 React tests, TypeScript/build and three real Chromium
workflows pass. Existing non-root Docker contexts and lockfiles are unchanged.

Current inherited policy retrieval returns 97 assignments; all 14 application
ARM resources retain the authorized `SecurityControl=Ignore` tag. Static role
review confirms unchanged registry-scoped AcrPull for API/web/refresh, AcrPush
for the deployer, Maps-account Data Reader and container-scoped native Cosmos
Data Contributor for API/refresh, and render/traffic reads only for the browser
identity. No additional permission, capacity or exception is requested.
No personal interactive Entra session has been tested; tenant and browser
policy still govern silent restoration.

## All validation checks pass

- [x] AZD installation, selected environment, authentication, subscription/location.
- [x] Official azure.yaml schema validation.
- [x] Aspire pre/post-provisioning checks not applicable.
- [x] Non-destructive real provision preview.
- [x] Frontend build and functional verification.
- [x] Existing Docker contexts, non-root users and checked-in lockfiles unchanged.
- [x] Secure remote-build mode package validation.
- [x] Complete Terraform preflight including authenticated state and real plan.
- [x] Existing policy/tag preservation and static data-plane role verification.

## Remembered-session rollout result

Verified: 2026-11-06T17:40:42-06:00.

Web update deployed:
https://ca-njk0ztnkmgrmn-web.icyflower-2a21f8a0.eastus2.azurecontainerapps.io/

`azd provision --no-prompt` completed the reviewed eight in-place diagnostic
reconciliations with zero additions/destruction. All three registry-scoped
AcrPull assignments were confirmed before `azd deploy web --no-prompt`.
Secure ACR remote build and deployment succeeded; `azd show` confirms endpoints.

Web revision `ca-njk0ztnkmgrmn-web--azd-1794008368` equals latest ready and is
healthy/running. Image:
`crnjk0ztnkmgrmn.azurecr.io/supply-chain-routing/web-demo:azd-deploy-1794008226`.
The deployed `index-VCdgS9LU.js` and `index-D0OQ3mso.css` match the validated
local build byte-for-byte. Live auth smoke passes: discovery/readiness available
and anonymous, invalid and spoofed credentials rejected.
Initial checks preceded revision readiness: readiness timed out and assets
still belonged to the old revision. After the new revision became ready,
standalone retries passed without configuration changes.

API revision remains `ca-njk0ztnkmgrmn-api--azd-1794006389`, latest equals ready;
API and refresh retain `api-demo:azd-deploy-1794006304`.
Live role verification confirms unchanged Maps-account Data Reader for API/
refresh, browser render/traffic reads only, and native Cosmos Data Contributor
at the scenario-container scope. All 14 application ARM resources retain the
authorized tag. No scopes, registration, scenarios or backend code changed.

71 frontend tests and three synthetic/local Chromium workflows pass; no actual
personal Entra login or browser-restart cookie persistence is claimed. Microsoft
Stay signed in, browser cookie rules and tenant policy control continued SSO.

## Previous shipment-plan clarity deployment (historical)

Previous status: Deployed

## Current scope

Modify the existing `demo` environment in East US 2, subscription
`0ec6c427-01d3-4462-ae56-fd9656157157`, application group `rg-scroute-eus2`.
Reuse Terraform with azd orchestration and secure ACR remote builds.
Autopilot continues the existing demo update; no new services, capacity,
regions, permissions, registration, infrastructure source or dependencies.

Deploy web only: explain the unchanged minimum-cost supplier-to-factory
allocation, rename the action Calculate shipment plan, show all recommended
shipments in blue with quantities, optional dashed slate alternatives, purple
inspection and magenta local disruption previews. Use a light grayscale basemap
and white route casings. Do not recolor every route for network-wide previews,
and show disruption targets only in the Disruptions tab.

Preserve the deployed API/refresh images, Cosmos data, authentication boundary,
single-tenant registration, Maps render/traffic role, all existing managed
identities and `SecurityControl=Ignore` tags. Route inspection must not submit
an optimization request or change persisted allocations.

## Current preparation checklist

- [x] Inspect actual optimizer, UI/map, deployment settings and existing tests.
- [x] Implement the frontend-only clarification without dependency changes.
- [x] Frontend lint/format/types, 64 tests and production build pass.
- [x] Complete desktop/mobile Chromium scenario and visual verification.
- [x] Run azure-validate workflow and record current proof.
- [x] Reconcile existing infrastructure as required by the deployment checklist,
  after a non-destructive preview; verify propagated AcrPull.
- [x] Deploy web only and verify ready revision, exact frontend assets and
  public readiness/auth boundaries. No actual user sign-in is claimed.

## Functional verification

Verified locally against the real unchanged FastAPI demo backend. All 64 React
tests, frontend lint/format/types/build and two real Chromium workflows pass.
Browser checks cover positive allocation visibility, default-hidden alternatives,
optional inspection without changing the plan, closure and +25-minute facility
delay recalculations, persistence and desktop/mobile overflow. Screenshot review
removed long inspection labels; compact quantities and color/line legend are
verified. SDK unit tests verify source separation, blue/white recommendation
layers, dashed slate alternatives, stable viewport and textual global previews.
No new operation or entrypoint requires a VS Code task change.

Existing Azure context was rechecked: selected azd `demo`, subscription and
tenant unchanged, East US 2, `rg-scroute-eus2`. Zero additional resources or
capacity requested; no regional quota increase is needed.

## Previous shipment-plan validation proof (historical)

Current evidence recorded: 2026-11-06T17:18:27-06:00.

The current azure-validate workflow ran the AZD recipe against the existing
Terraform-backed `demo` environment. `azd version`, selected environment/context,
`azd auth login --check-status` and official azure.yaml schema validation pass.
`azd provision --preview --no-prompt` succeeds: zero additions, eight in-place
diagnostic-destination drift reconciliations, zero destruction; no app image,
network, identity, registration, role or scope changes. Preview output is saved
in the session's `files/shipment-provision-preview.log`.

The complete `validate-terraform.sh infra` preflight passes all ten checks using
azd-generated `demo.conf.json` backend configuration and `main.tfvars.json`.
This includes authenticated remote-state access, format/validate, real plan,
state list, JSON syntax and unresolved-template scan. No warnings/errors.
The temporary `infra/tfplan` was removed.

Frontend ESLint, Prettier, 64 React tests, TypeScript and production build pass.
Two real Chromium workflows pass, using the unchanged FastAPI backend in
deterministic local mode. Desktop/mobile screenshots inspected; quantity-only
labels avoid inspection clutter. Dockerfiles retain non-root users and correct
build contexts/lockfiles. `azd package --all --no-prompt` succeeds with secure
remote ACR builds selected. The existing Maps SDK bundle-size advisory remains.

Static roles remain unchanged and sufficient: resource-scoped AcrPull for
API/web/refresh, AcrPush for the deployer, Maps Data Reader and container-scoped
native Cosmos Data Contributor for API/refresh, and render/traffic reads only
for the separate browser identity. All 14 application ARM resources retain
the user-authorized exception tag; existing policy assignments were retrieved.
No new policy exception, management privilege, public ingress or service
permission is requested. Real personal delegated cloud acceptance remains
outside the deterministic browser fixture coverage.

## All validation checks pass

- [x] AZD installation, selected environment, authentication, subscription/location.
- [x] Official azure.yaml schema validation.
- [x] Aspire pre/post-provisioning checks not applicable.
- [x] Non-destructive real provision preview.
- [x] Frontend build and functional verification.
- [x] Docker contexts, non-root users and checked-in package/uv lockfiles.
- [x] Secure remote-build mode package validation.
- [x] Terraform complete preflight including authenticated state and real plan.
- [x] Existing policy/tag preservation and static data-plane role verification.

## Shipment-plan rollout result

Verified: 2026-11-06T17:25:17-06:00.

Web update deployed:
https://ca-njk0ztnkmgrmn-web.icyflower-2a21f8a0.eastus2.azurecontainerapps.io/

`azd provision --no-prompt` completed with zero additions, eight in-place
diagnostic reconciliations and zero destruction. All three registry-scoped
AcrPull assignments were confirmed before `azd deploy web --no-prompt`.
The secure ACR remote build and web deployment succeeded.

Latest web revision `ca-njk0ztnkmgrmn-web--azd-1794007393` equals latest ready,
is healthy and running. Image:
`crnjk0ztnkmgrmn.azurecr.io/supply-chain-routing/web-demo:azd-deploy-1794007265`.
API revision remains `ca-njk0ztnkmgrmn-api--azd-1794006389`, latest equals ready;
API/refresh still share the unchanged `api-demo:azd-deploy-1794006304` image.
`azd show` confirms the expected endpoints.

Deployed JS (`index-Ch6_iv7H.js`) and CSS (`index-D0OQ3mso.css`) match the
validated local build byte-for-byte. The standalone auth smoke passes:
readiness/discovery available and anonymous, invalid and spoofed credentials
rejected. Initial HTTP checks timed out immediately after deployment; settled
standalone retries passed without configuration changes.

Live role verification confirms unchanged Maps-account-scoped Data Reader for
API/refresh, browser render/traffic reads only (no management actions), and
native Cosmos Data Contributor for API/refresh at the scenario-container scope.
No persisted scenario or permission was modified by the UI change.

Local Chromium covers actual scenario operations and mocked profile behavior;
SDK source/style behavior has focused unit coverage. No completed interactive
user cloud login or authenticated live-map visual session is claimed.

## Previous Fluent map workspace deployment (historical)

Previous status: Deployed

## Current change and deployment context

Update the existing `demo` environment in subscription
`0ec6c427-01d3-4462-ae56-fd9656157157`, tenant
`66beb9f0-9df6-4ded-8e48-126b39813500`, East US 2,
application group `rg-scroute-eus2`. Reuse the current Terraform/azd project,
private state container and existing resources; do not initialize a new project.

Deploy the square-corner Fluent UI map-first workspace, Houston-area default
scenario, synchronized named route/facility targets, traffic/basemap/fit controls,
and aligned account photo with `Howdy First Last!`. Add only delegated Graph
`User.Read` permission metadata to the existing registration and enable traffic
read on the existing browser Maps role for the new overlays. Graph tokens remain
separate from API tokens. Do not create consent grants, application permissions,
credentials or a new registration. Existing sessions can explicitly load the
photo if further consent is needed. Actual personal photo access requires a
delegated signed-in session and is not claimed by mocked browser tests.

Preserve workload identities, internal API ingress and the explicitly
authorized `SecurityControl=Ignore` tags. No new ARM services or regional capacity
are required. Preview the actual change before applying; use secure ACR remote
builds, confirm visible AcrPull and verify healthy revisions/auth boundaries.
Autopilot continues the existing approved implementation/rollout without
reselecting subscription, changing policies or granting unrelated privileges.

Local validation: 181 warning-free Python tests with Ruff/format/mypy;
59 frontend tests and build; 11 mocked Terraform plans, warning-free validation
and TFLint; two Chromium desktop/mobile flows including mocked Graph profile,
closure and facility delay. Visual inspection led to verified sidebar intrinsic
sizing and schematic-label fixes; no horizontal page/sidebar overflow remains.

## Current validation checklist

- [x] All validation checks pass
  - [x] azd installed; existing environment, authentication, subscription and region checked.
  - [x] Official azure.yaml schema validation.
  - [x] Aspire pre/post-provisioning checks not applicable.
  - [x] Real provision preview: one Graph permission-metadata addition, eight
    in-place diagnostic-destination drift reconciliations, zero destruction.
    No app image, identity, network or role changes appear in the preview.
  - [x] Python/frontend builds and Docker build-context/lockfile checks.
  - [x] `azd package --all --no-prompt` in secure remote-build mode.
  - [x] Complete Terraform preflight including remote state/plan.
  - [x] Existing policy/tag preservation and static data-plane role verification.
  - [x] Traffic follow-up: 11 mocked plans and real preview/preflight pass;
    existing role updated in place, no additions, replacements or deletions.

## Previous Fluent validation proof (historical)

Evidence recorded: 2026-11-06T16:45:16-06:00. The azure-validate workflow completed.

The current azure-validate workflow ran the real azd preview successfully:
one delegated Graph permission-metadata resource, eight in-place reconciliations
of existing diagnostic destination settings, no replacement or deletion. The
complete Terraform preflight passed all ten checks using azd-generated backend
configuration and variables, including authenticated state access and real plan.
Terraform format/validate, ten mocked plans and recursive TFLint are warning-free.

Official azure.yaml schema validation, `azd auth login --check-status`,
`azd package --all --no-prompt`, `uv build` and Node 22 production build pass.
Dockerfiles retain non-root users and correct contexts/lockfiles; secure ACR
remote builds remain selected. Ruff/format/mypy, 181 warning-free Python tests,
59 React tests, frontend lint/format/types and two real Chromium workflows pass.
Screenshots confirm desktop/mobile header alignment, readable named targets and
no horizontal page/sidebar overflow; browser tests verify a facility delay adds
25 minutes and a closure removes only its selected candidate. Profile browser
coverage uses mocked Graph and does not claim a personal delegated cloud session.

Static RBAC remains verified: registry-scoped AcrPull for API/web/refresh;
Maps Data Reader and container-scoped native Cosmos Data Contributor for API and
refresh; only render and traffic Maps reads for the separate browser identity.
No assignment IDs/scopes change. Policy assignments were retrieved; the existing explicit
exception tag remains on the app group/state account, with shared keys and
anonymous Blob access disabled. No policy, ingress or network changes are planned.
The existing Maps SDK large-bundle advisory remains non-blocking.

### Traffic overlay authorization follow-up

The UI/API deployment succeeded with healthy revisions and exact verified
frontend artifacts. Live verification identified that SDK v3 requests
`/traffic/incident/tile/pbf`; the provider classifies Traffic APIs separately
from Render APIs. The previous render-only browser role is therefore
insufficient for the newly added traffic control.

Add exactly `Microsoft.Maps/accounts/services/traffic/read` alongside render
read on the existing browser custom role. Preserve its definition/assignment
IDs and Maps-account scope. No management, search, route or weather-service
permissions are added. Update the role's display name/description and add a
mocked-plan boundary test. Align backend configuration wording, then redeploy
only API after the role update; frontend assets do not change.

Follow-up validation: Terraform format/validate, 11 mocked plans, TFLint and the
complete real-state preflight all pass without warnings. Real azd preview shows
zero additions, nine in-place changes (one custom role plus the existing
diagnostic-destination drift), and zero destruction. The role and assignment IDs,
principal and account scope are preserved.
Ruff/format/mypy, 71 targeted warning-free API/auth tests, `uv build` and
`azd package api --no-prompt` pass after the backend wording change.
Follow-up evidence recorded: 2026-11-06T17:00:26-06:00.

Sources: [Web SDK traffic overlays](https://learn.microsoft.com/azure/azure-maps/map-show-traffic),
the installed SDK v3 incident tile URL, and the live `Microsoft.Maps` provider
operation descriptions for `services/render/read` and `services/traffic/read`.

## Fluent rollout result

The Fluent/Houston update is deployed:
https://ca-njk0ztnkmgrmn-web.icyflower-2a21f8a0.eastus2.azurecontainerapps.io/

Initial provision added only the delegated Graph permission metadata and
reconciled eight diagnostic settings, with zero destruction. The traffic
follow-up updated the existing custom role and those diagnostic settings in
place: zero additions, nine changes, zero destruction. All 14 application ARM
resources retain `SecurityControl=Ignore`.

Secure ACR remote builds deployed the verified frontend and final backend.
Final API revision `ca-njk0ztnkmgrmn-api--azd-1794006389` is healthy and running;
web revision `ca-njk0ztnkmgrmn-web--azd-1794005383` remains healthy.
Latest and ready revisions match. API and refresh share image
`crnjk0ztnkmgrmn.azurecr.io/supply-chain-routing/api-demo:azd-deploy-1794006304`;
web uses
`crnjk0ztnkmgrmn.azurecr.io/supply-chain-routing/web-demo:azd-deploy-1794005250`.

Live checks verify readiness/discovery and rejection of anonymous, invalid and
spoofed credentials. Actual browser-identity requests return HTTP 200 for both
incident and flow tiles. The custom role still has exactly render/traffic data
reads, no management actions, and its assignment remains Maps-account scoped.
Deployed JS/CSS match the locally validated build byte-for-byte; Chromium
verified the actual Microsoft sign-in prompt and code/S256 PKCE request.

Existing saved scenarios are preserved; use **Load Houston sample** for the new
defaults. Existing sessions may need **Load profile photo** and delegated
Microsoft consent. Real personal photo access, completed interactive user login
and authenticated cloud optimization are not claimed; deterministic Graph and
full scenario browser tests use the documented local fixtures.

## Previous Entra deployment record (historical)

The following describes the successfully deployed authentication baseline before
the current Fluent/Houston update and its optional Graph profile permission.

## Scope and architecture

Modify the implemented React/FastAPI Container Apps demo. Use single-tenant
Entra authentication with MSAL authorization-code flow and PKCE in React.
FastAPI validates delegated bearer tokens against tenant signing keys, issuer,
audience, expiry, tenant and scope. No client secret or Graph permissions are
needed. Terraform manages the app registration, service principal, scope,
production SPA redirect and runtime settings.

Workload managed identities and the separate Maps browser identity remain
unchanged. Authenticated tenant users retain the shared scenario semantics of
this demo; per-user scenario ownership and app-only access are out of scope.
Local deterministic demo mode may explicitly disable authentication.

## Azure context and deployment recipe

- Subscription: current `jordanbean-demo-subscription`.
- Region: eastus2 unless existing project-specific state establishes otherwise.
- Recipe: existing Terraform with azd orchestration; do not reinitialize templates.
- No local azd environment or existing Container Apps were found in the active
  subscription. This is a first live deployment, not an update to a known app.
- Use dedicated project resource groups and state storage; do not repurpose
  unrelated resources. Create the resource group outside Terraform as required.
- Check regional capacity and policy before provisioning.
- The user explicitly requested implementation, registration and redeployment;
  autopilot authorizes execution without another interactive approval.

Selected local azd environment: `demo`. Dedicated application group:
`rg-scroute-eus2`; state group: `rg-scroute-state-eus2`; state storage account:
`stscroute0ec6c4`, container `tfstate`. Both groups, the storage account and the
private container now exist with the explicitly authorized exception tag.
The active principal has subscription Owner,
role-assignment and Storage Blob Data Contributor permissions.

## Capacity and policy evidence

The quota CLI was attempted first, but its missing extension could not install
(pip status 3, including retry with the public package index). Provider-native
ARM usage is therefore the fallback, not an assumption of unlimited capacity.

| Resource | Addition | Observed usage / limit | Evidence |
| --- | --- | --- | --- |
| ACA environments | 1 | 0 / 50 | Microsoft.App eastus2 usages, API 2025-01-01 |
| State storage accounts | 1 | 5 / 250 | Microsoft.Storage eastus2 usages, API 2023-05-01 |
| Cosmos accounts | 1 | 1 / 250 | ARM inventory and Cosmos concepts-limits documentation |
| API/web/job | 2 apps, 1 job | New environment; bounded consumption sizing | Existing explicit tfvars; ARM validates per-environment capacity |
| ACR | 1 Premium | 3 existing | ARM inventory; provider usage endpoint unsupported |
| Maps | 1 G2 | 0 existing | ARM inventory |
| Monitoring/identities | 1 workspace, 1 Insights, 4 identities | Dedicated resource group | No shared-resource mutation |
| Entra application | 1 registration, 1 service principal | Tenant write permission checked by provision | No secrets or Graph data permissions |

East US 2 supports Container Apps according to the provider's resource-location
metadata. Microsoft.App, Maps, DocumentDB and ContainerRegistry are registered.
Subscription assignments include private-DNS DINE policies; preserve the
repository's private endpoint lifecycle rules. No quota increase, policy change
or unrelated-resource modification is planned.

Inherited management-group policy inspection subsequently confirmed an active
`MCAPSGovDeployPolicies` assignment. Its `StorageAccount_PublicNetwork_Modify`
policy replaced the new state account's requested public access with `Disabled`.
The corresponding `Microsoft.Authorization/policies/modify/action` event records
that exact field replacement. Cosmos has an equivalent enforced modification.
Both policies recognize `SecuredByPerimeter`, but a compliant perimeter/private
network design and connected deployment path have not been supplied.

The user subsequently explicitly requested `SecurityControl=Ignore` on the demo
Azure resources and another deployment attempt. Apply this operator-authorized
exception to the two dedicated groups and state account, and persist the tag in
Terraform's shared tag map for all app-owned ARM resources. Do not tag shared
networking, policy definitions or unrelated resources. Re-enable the deliberately
selected public state endpoint while keeping shared keys and anonymous access
disabled. The earlier networking blocker is being retried under this authorization.

## Execution checklist

- [x] Inspect repository, active tenant/subscription and deployment state.
- [x] Implement authenticated API and deterministic signing-key tests.
- [x] Implement React sign-in/sign-out, bearer requests and authenticated SSE.
- [x] Implement Terraform registration and runtime configuration.
- [x] Update documentation, smoke checks and developer configuration.
- [x] Validate application, browser and Terraform behavior.
- [x] Invoke azure-validate, then azure-deploy.
- [x] Provision registration/resources, deploy and verify live authentication.
  Live authentication boundary and Microsoft sign-in entry are verified;
  interactive account login remains an operator acceptance step.

## All validation checks pass

- [x] Terraform/Azure CLI installed and authenticated.
- [x] azd environment explicitly selects the active subscription and East US 2.
- [x] Official azure.yaml schema validation.
- [x] Terraform format, syntax validation, template scan and JSON syntax.
- [x] Application builds, local tests and Docker build-context/lockfile checks.
- [x] `azd package --all --no-prompt` succeeds; remote image builds occur later.
- [x] Static data-plane RBAC verification.
- [x] Remote backend initialization, real plan and state access.
- [x] `azd provision --preview --no-prompt`: 55 additions, no changes/deletions.
- [x] Explicitly authorized policy exception restores selected public networking.

## Static role verification

API/refresh have Maps Data Reader and Cosmos native NoSQL Data Contributor
scoped to the scenario container. API/web/refresh have registry AcrPull.
The separate browser identity has only the custom Maps render data action.
The deployer has registry AcrPush; state uses Entra Blob Data Contributor.
The new registration has delegated user scope only, no Graph data permissions
or client credentials. No access keys were introduced. The only policy exception
is the resource/group tag explicitly requested by the operator.

## Historical validation proof

Preparation verification:

- Python: Ruff, formatting, mypy, 180 warning-free tests, 93.94% coverage and
  `uv build` pass.
- Terraform: format, init, JSON validate (zero warnings/errors), 10 mocked plans,
  recursive TFLint and three deployment-hook tests pass.
- Real local Vite-to-API smoke with authentication enabled: discovery/readiness
  work; anonymous requests, invalid bearer tokens and spoofed platform headers
  all receive 401 with Bearer challenge. Functional smoke refuses to proceed
  without a delegated token. Temporary servers were stopped.
- Shell syntax, actionlint and VS Code task JSON validation pass.
- React: 32 tests, lint, formatting, types and production build pass on Node 22.
  Shipped dependencies have zero npm audit findings; npm reports ten moderate
  findings in development tooling, which is not included in the Nginx image.
- Integrated real Chromium walkthrough passes: discovery, seed, edit,
  optimization, closure, comparison and reload. Local test processes stopped.
  Existing large Maps SDK bundle advisory remains.

Never claim deployment or interactive Entra sign-in without corresponding
evidence. Previous full container builds encountered daemon-side package TLS
failures; azd is now configured for secure ACR remote builds.

Azure-validate execution on 2026-11-06:

| Check | Command | Result |
| --- | --- | --- |
| Schema | Azure MCP `validate_azure_yaml` | Pass |
| Package preparation | `azd package --all --no-prompt` | Pass; no local image artifacts in remote-build mode |
| Real infrastructure preview | `azd provision --preview --no-prompt` | Blocked: backend Blob listing HTTP 403 |
| Required Terraform preflight | `validate-terraform.sh infra` with generated backend config | Tools/auth/fmt/validate/template/JSON pass; init/plan/state fail due inaccessible backend |
| Enforced policy evidence | Activity log policy modify event and inherited policy definitions | Storage public access forcibly disabled; Cosmos subject to equivalent policy |

The first validation attempt did not complete successfully. After the user's
explicit exception-tag authorization, the retry passed:

| Check | Command | Result |
| --- | --- | --- |
| Resource tags | Actual group/account tags and Terraform plan JSON | All 13 taggable planned app ARM resources have `SecurityControl=Ignore`; unrelated resources untouched |
| State access | `az storage container create/show --auth-mode login` | Private `tfstate` container accessible; shared keys/anonymous access disabled |
| Real preview | `azd provision --preview --no-prompt` | Pass: 55 additions, zero changes/deletions, no warnings |
| Complete Terraform preflight | `validate-terraform.sh infra` with generated backend/tfvars | All ten checks pass, including init/plan/state |
| Terraform regression | fmt, JSON validate, `terraform test`, TFLint | Zero warnings/errors; 10 mocked plans pass |
| Package preparation | `azd package --all --no-prompt` | Pass in remote-build mode |

Validated by: azure-validate workflow, 2026-11-06. All recipe checks now pass.

## Deployment and live role verification

`azd provision --no-prompt` completed with 55 additions, zero changes/deletions.
The three workload identities have visible AcrPull before image deployment.
API/refresh have Maps Data Reader and scoped Cosmos native Data Contributor;
the separate browser identity has only the custom render role.
All 14 listed application ARM resources, the dedicated groups and state account
have the approved exception tag. Cosmos/state keys and anonymous Blob access
remain disabled. The pre-created app group also has `azd-env-name=demo` so
`azd show` discovers the actual endpoints.

`azd deploy --no-prompt` securely built both images in ACR and deployed them.
Error recovery fixed schema drift between CLI template reads and pinned ARM
writes, explicit activation of image entry points, and ACA Host-based proxy
routing. Five hook regressions and two real Nginx Host/Origin cases pass.
The local Docker host still emits its existing AIO compatibility notice.
Actionlint, shell syntax and VS Code task JSON validation pass.

Both latest revisions are ready. The refresh image exactly matches API image
`api-demo:azd-deploy-1794001816`; manual execution
`ca-njk0ztnkmgrmn-refresh-5seaage` succeeded.
API startup confirms Cosmos access and Azure Monitor telemetry export.

- Web: https://ca-njk0ztnkmgrmn-web.icyflower-2a21f8a0.eastus2.azurecontainerapps.io/
- Entra client ID: `2c924cbc-ad1d-4731-a699-8705627a882c`.
- Registration: single tenant, v2 delegated scope, no secrets, exact SPA redirect.
- `scripts/smoke-auth.sh`: readiness/discovery pass; anonymous, invalid and
  spoofed credentials receive 401 Bearer challenges.
- Chromium: real sign-in gate, expected tenant/client/callback, authorization
  code with S256 PKCE, and Microsoft email prompt pass.

No interactive user login, delegated token exchange, or authenticated cloud
seed/optimization walkthrough was performed. These remain manual acceptance;
no client preauthorization, fake token or production auth bypass was added.
