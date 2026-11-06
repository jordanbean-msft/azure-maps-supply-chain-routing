# Entra authentication deployment

Status: Blocked — remote state access denied by enforced network policy

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
`stscroute0ec6c4`, intended container `tfstate`. Both groups and the empty storage
account were created; the container could not be created.
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

## Execution checklist

- [x] Inspect repository, active tenant/subscription and deployment state.
- [x] Implement authenticated API and deterministic signing-key tests.
- [x] Implement React sign-in/sign-out, bearer requests and authenticated SSE.
- [x] Implement Terraform registration and runtime configuration.
- [x] Update documentation, smoke checks and developer configuration.
- [x] Validate application, browser and Terraform behavior.
- [ ] Invoke azure-validate, then azure-deploy.
- [ ] Provision registration/resources, deploy and verify live authentication.
  Blocked before Terraform apply: state Blob requests return HTTP 403. No
  registration, Container App, ACR, Maps or Cosmos account was created.

## All validation checks pass

- [x] Terraform/Azure CLI installed and authenticated.
- [x] azd environment explicitly selects the active subscription and East US 2.
- [x] Official azure.yaml schema validation.
- [x] Terraform format, syntax validation, template scan and JSON syntax.
- [x] Application builds, local tests and Docker build-context/lockfile checks.
- [x] `azd package --all --no-prompt` succeeds; remote image builds occur later.
- [x] Static data-plane RBAC verification.
- [ ] Remote backend initialization, real plan and state access: HTTP 403.
- [ ] `azd provision --preview --no-prompt`: same backend HTTP 403.
- [ ] Policy-compatible deployment networking: required before proceeding.

## Static role verification

API/refresh have Maps Data Reader and Cosmos native NoSQL Data Contributor
scoped to the scenario container. API/web/refresh have registry AcrPull.
The separate browser identity has only the custom Maps render data action.
The deployer has registry AcrPush; state uses Entra Blob Data Contributor.
The new registration has delegated user scope only, no Graph data permissions
or client credentials. No access keys or policy exemptions were introduced.

## 7. Validation proof

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

Validation did not complete successfully. Do not mark this plan Validated or
invoke application deployment until approved networking is available. No
policy assignment, exemption, shared network or unrelated resource was changed.

## Resumption requirements

Provide an approved, reachable state endpoint and policy-compliant Cosmos
networking: private endpoints with a connected runner, or an approved enforced
NSP configuration. Preserve Entra-only storage authentication and the existing
Terraform state conventions. Then create `tfstate`, rerun azure-validate, and
invoke azure-deploy for provisioning, registration creation and image deployment.
The two dedicated resource groups and empty state account remain available.
