# Entra authentication deployment

Status: Executing

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
`stscroute0ec6c4`, container `tfstate`. These groups do not yet exist.
The account name is available. The active principal has subscription Owner,
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

## Execution checklist

- [x] Inspect repository, active tenant/subscription and deployment state.
- [ ] Implement authenticated API and deterministic signing-key tests.
- [ ] Implement React sign-in/sign-out, bearer requests and authenticated SSE.
- [ ] Implement Terraform registration and runtime configuration.
- [ ] Update documentation, smoke checks and developer configuration.
- [ ] Validate application, browser and Terraform behavior.
- [ ] Invoke azure-validate, then azure-deploy.
- [ ] Provision registration/resources, deploy and verify live authentication.

## Validation proof

Pending implementation. Never claim deployment or interactive Entra sign-in
without corresponding evidence. Previous full container builds encountered
daemon-side package download TLS failures; use secure remote builds if needed.
