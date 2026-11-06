# Fluent map workspace deployment

Status: Validated

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

## 7. Validation Proof

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
