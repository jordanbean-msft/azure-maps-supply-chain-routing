# Azure deployment

Terraform prepares resources; `azd` builds and deploys the API/web images.
Microsoft Entra sign-in is required for deployed data APIs.
Use a pre-created resource group and a separate, pre-created Blob state store.
Never put credentials in tfvars, images, JavaScript or repository variables.

## Prerequisites

- Terraform 1.14+ for the included mock tests (configuration requires 1.9+),
  Azure CLI with the Container Apps extension, Azure Developer CLI, Python 3 and
  Docker. The chosen region must support ACA, ACR and Cosmos NoSQL serverless.
- Register Microsoft.App, ContainerRegistry, Maps, DocumentDB, ManagedIdentity,
  Insights, OperationalInsights and Network resource providers as appropriate.
- The deployment principal needs resource provisioning rights, custom role
  definition/assignment permissions, identity assignment rights, and **Storage
  Blob Data Contributor** on the remote state container. Its
  `AZURE_PRINCIPAL_ID` is the Entra **object ID**, not a client/application ID.
  Terraform grants that principal AcrPush.
- The principal also needs permission to create/own an Entra application and
  service principal. Terraform manages the secretless SPA/API registration;
  Azure subscription Owner does not automatically grant directory permissions.
- Private deployments need a network-connected build/deployment runner with
  working private DNS. Hosted GitHub runners cannot reach private ACR/web.

Registry research selected AzureRM **5.13.0**, AzureCAF **2.0.0**, and Time
**0.14.2**, with matching pessimistic constraints in root/child modules.
Preserve `infra/.terraform.lock.hcl`, including Linux AMD64/ARM64 checksums.
The authentication module additionally pins the AzureAD provider.

## azd context and remote state

These are operator instructions, not evidence of deployment:

```sh
azd init
azd env set AZURE_SUBSCRIPTION_ID "<subscription-id>"
azd env set AZURE_TENANT_ID "<tenant-id>"
azd env set AZURE_LOCATION "eastus2"
azd env set AZURE_RESOURCE_GROUP "<existing-app-resource-group>"
azd env set AZURE_PRINCIPAL_ID "<deployment-principal-object-id>"
azd env set RS_RESOURCE_GROUP "<existing-state-resource-group>"
azd env set RS_STORAGE_ACCOUNT "<existing-state-storage-account>"
azd env set RS_CONTAINER_NAME "<existing-state-container>"
azd env set RS_PROJECT_NAME "supply-chain-routing"
```

`AZURE_ENV_NAME` is selected by azd. `AZURE_LOCATION` must match the existing
resource group's location. State is
`${RS_PROJECT_NAME}/${AZURE_ENV_NAME}.tfstate`; azd substitutes backend values
from `infra/provider.conf.json`. The backend uses Entra, not storage keys.

### Enforced organization networking

Check inherited management-group policies, not only subscription assignments.
A policy can modify `publicNetworkAccess` to `Disabled` even when the create
request explicitly enables it. This affects both remote-state access and
application data services. A subscription Owner role does not bypass network
policy, and granting more Blob roles will not fix a network-denied 403.

Use approved private endpoints with a connected deployment runner, or an
approved enforced Network Security Perimeter design where supported. Do not
disable governance, add exemption tags, enable shared keys or move state into an
unrelated open storage account to work around the restriction. Establish a
reachable state backend before provisioning; otherwise Terraform cannot create
the app registration or application resources.

### Private-first configuration

The safe operator configuration is **false**:

```sh
azd env set PUBLIC_NETWORK_ACCESS_ENABLED "false"
azd env set ACA_INFRASTRUCTURE_SUBNET_ID "/subscriptions/<id>/resourceGroups/<network-rg>/providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/<aca>"
azd env set PRIVATE_ENDPOINT_SUBNET_ID "/subscriptions/<id>/resourceGroups/<network-rg>/providers/Microsoft.Network/virtualNetworks/<vnet>/subnets/<endpoints>"
```

Both subnets and their VNet must already exist. Supply an appropriately sized,
`Microsoft.App/environments`-delegated ACA subnet and a separate endpoint subnet.
Terraform never creates the resource group, VNet, subnets, private DNS zones,
links or zone groups. Platform networking must allow subnet joins and configure
routes/firewalls/DNS. Existing DINE policies must attach the pre-existing ACR,
Cosmos and Azure Monitor DNS zones. Every endpoint ignores
`private_dns_zone_group` changes.

Private mode disables public ACR/Cosmos access and deploys their private
endpoints, plus an Azure Monitor Private Link Scope linked to the workspace and
Insights with its own endpoint. ACR is Premium because private endpoints
require it. ACA uses an internal load balancer: web ingress is external to the
ACA environment, **not internet-public** in private mode. The platform must
configure the environment-domain wildcard DNS to the internal static IP for
private browser/runner access.

**Azure Maps does not support private endpoints.** Its global Entra-protected
HTTPS endpoint remains public in either mode, with key authentication disabled
and exact browser CORS origins. Private workloads require controlled HTTPS
egress to Maps, Entra, MCR for bootstrap and required Azure platform endpoints.
This is not a completely air-gapped solution.

### Explicit public demonstration

```sh
azd env set PUBLIC_NETWORK_ACCESS_ENABLED "true"
azd env set ACA_INFRASTRUCTURE_SUBNET_ID ""
azd env set PRIVATE_ENDPOINT_SUBNET_ID ""
```

This deliberately enables internet web ingress and public ACR/Cosmos
endpoints; it is not the recommended private configuration. All data endpoints
still require Entra authorization. ACR admin credentials, Maps keys and Cosmos
local/key authentication are disabled.

The API always has **internal ingress on 8000**. Only Nginx web ingress on
**8080** is browser-accessible. Its `API_INTERNAL_URL` is an HTTPS origin with
no `/api` or trailing slash; Nginx proxies API requests and SSE.

### User sign-in

Terraform creates a single-tenant SPA/API registration, exposes delegated
`access_as_user`, and registers the web origin plus `/` as the SPA redirect.
It enables `AUTH_ENABLED` and injects `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID` and
`ENTRA_API_SCOPE` into the API. These are nonsecret IDs, not workload credentials.
React discovers them at runtime; no client secret or frontend rebuild is needed.
Tenant consent policies may require administrator approval before the first
sign-in. See [authentication](authentication.md) for access boundaries.

### GitHub Actions inputs

Alongside the Azure and `RS_*` repository/environment variables above, use
**AZD_TERRAFORM_ENV** as the JSON string map consumed by the deployment
workflow to hydrate all additional tfvars placeholders. Private example:

```json
{
  "PUBLIC_NETWORK_ACCESS_ENABLED": "false",
  "ACA_INFRASTRUCTURE_SUBNET_ID": "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/network/providers/Microsoft.Network/virtualNetworks/shared/subnets/aca",
  "PRIVATE_ENDPOINT_SUBNET_ID": "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/network/providers/Microsoft.Network/virtualNetworks/shared/subnets/endpoints"
}
```

For the explicit public demo, set `"PUBLIC_NETWORK_ACCESS_ENABLED": "true"`
and both subnet strings to `""`. These identifiers are not credentials.
Configure GitHub OIDC for Azure CLI (`azure/login`) and azd
(`azd auth login --federated-credential-provider github`), without client
secrets. On fresh application-deployment runners, select the environment and
run `azd env refresh` to restore infrastructure outputs and mappings.

## Validation and deployment

```sh
terraform -chdir=infra init -backend=false
terraform -chdir=infra fmt -check -recursive
terraform -chdir=infra validate
terraform -chdir=infra test
tflint --chdir=infra --recursive
sh infra/tests/deploy-refresh.test.sh
# Only after context, costs, networking and permissions have been reviewed:
azd provision
azd deploy
```

`azure.yaml` requests ACR remote builds, avoiding dependence on the local
Docker daemon's network/TLS configuration. This requires ACR Tasks permissions
and access to public package registries. For a private-only registry, use a
connected build agent and change both `docker.remoteBuild` values to `false`,
unless a suitable private ACR Tasks agent pool is configured.

Provisioning uses an immutable Microsoft Python image and an explicit bootstrap
HTTP server so the configured ports/probes work before application images
exist. **Provisioning is not application deployment.** The bootstrap page
instructs the operator to deploy; actual dependency readiness is established
only after deployment. The job cannot execute refresh until the first API
deploy; its initial bounded executions can fail because the bootstrap image
does not contain the refresh module.

Service postdeploy hooks run `infra/scripts/deploy-refresh.sh api|web`.
They remove only the provisioning command override, activating the image's
entry point. The API hook reads the **deployed API image** from its Azure
resource and updates the job to that exact image reference with
`python -m template_repository.refresh`. It neither rebuilds a job image nor
changes the job identity/environment. The hook rejects `latest`, untagged and
foreign-registry images; deployment tags must remain immutable. It clears old
revision suffixes before changing templates. This also runs for
`azd deploy api`, not just a full deploy.

Terraform ignores only deployment-managed images and app command overrides,
not resource sizing, runtime settings, probes, identities or RBAC.
Allow the new app revisions to become healthy before smoke tests. Retry a
failed API synchronization using `azd hooks run postdeploy --service api` or,
with azd environment values exported, `sh infra/scripts/deploy-refresh.sh api`.
The postdeploy patch uses Azure CLI authentication, so both CLI and azd must
be authenticated under the deployment identity.

## Runtime configuration and outputs

`infra/main.tfvars.json` explicitly defines deployment specifications:
serverless Cosmos with `/scenario_id` partition and positive 24-hour TTL;
API 0.5 CPU/1 GiB and one warm replica; web 0.25 CPU/0.5 GiB and 0–2 replicas;
refresh every 30 minutes (UTC), 960-second timeout, one retry, five scenarios.
Keep API replicas at one until cross-process claiming/request limits exist.

API/refresh receive `APP_MODE=live`, workload-specific `AZURE_CLIENT_ID`,
`AZURE_MAPS_CLIENT_ID`, `COSMOS_ENDPOINT`, `COSMOS_DATABASE`, `COSMOS_CONTAINER`,
`APPLICATIONINSIGHTS_CONNECTION_STRING`, `TELEMETRY_ENABLED=true` and explicit
`workloads.backend_env` bounds: scenario/snapshot TTL, request size, run timeout,
concurrency/rate limits and Maps cache interval. Developer credentials are off.
Refresh gets its own identity and `REFRESH_ENABLED`/`REFRESH_MAX_SCENARIOS`.

API, refresh and web have independent managed identities/AcrPull. API/refresh
have Maps Data Reader and Cosmos native NoSQL Data Contributor scoped to the
scenario container (`azurerm_cosmosdb_sql_role_assignment`, not an ARM role).
A fourth, separate browser identity is attached only to the API, assigned a
custom render-only Maps data role, and supplied as `MAPS_BROWSER_CLIENT_ID`.
Browser tokens do not expose routing/weather privileges.
`MAPS_ALLOWED_ORIGINS` is an exact JSON origin allowlist including the web
hostname. No Key Vault is needed: the only permitted exporter connection string
is stored as an ACA secret; there are no application service keys.

Root outputs captured into the azd environment:

| Purpose | Output names |
| --- | --- |
| Existing group | `AZURE_RESOURCE_GROUP` |
| Registry | `AZURE_CONTAINER_REGISTRY`, `AZURE_CONTAINER_REGISTRY_ENDPOINT` |
| ACA environment | `AZURE_CONTAINER_APPS_ENVIRONMENT_ID`, `AZURE_CONTAINER_APPS_ENVIRONMENT_NAME` |
| Hook mapping | `AZURE_CONTAINER_APP_API_NAME`, `AZURE_CONTAINER_APP_WEB_NAME`, `AZURE_CONTAINER_APP_REFRESH_JOB_NAME` |
| Endpoints | `SERVICE_WEB_URI` (browser/smoke), `SERVICE_API_URI` (internal only) |
| Maps | `AZURE_MAPS_CLIENT_ID` |
| User authentication | `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_API_SCOPE` |
| Cosmos | `COSMOS_ENDPOINT`, `COSMOS_DATABASE`, `COSMOS_CONTAINER` |
| Monitoring | `APPLICATIONINSIGHTS_CONNECTION_STRING`, `AZURE_LOG_ANALYTICS_WORKSPACE_ID` |

Sensitive Terraform outputs remain usable by azd; do not dump the full
environment or state into CI logs.

## Diagnostics and verification boundaries

The monitoring module always provisions Log Analytics plus workspace-based
Application Insights. Supported diagnostic categories/metrics are discovered
and exported to the shared workspace. Resource-specific tables are selected
where available; Maps and app/job metrics use AzureDiagnostics where no dedicated
log tables apply. ACA environment console/platform logs use Azure Monitor
diagnostics, not a second direct Log Analytics destination.

API/refresh initialize Azure Monitor OpenTelemetry; the environment also
receives native Dapr Insights configuration (Dapr itself is not enabled).
Nginx console/access logs flow to LAW; Nginx has no native Python/Insights agent.
Identities, RBAC, private endpoints and the Private Link Scope have no native
Insights instrumentation. Cosmos database/container diagnostics come from the
account. ACR, Cosmos and Maps have no application-host Insights agent; backend
SDK dependencies are traced. Maps Usage metrics cannot be exported by
diagnostic settings; use the Maps metrics blade and application transaction
counters. Quotas, replica bounds and TTL are **not a hard spending cap**.
Review overlapping Insights/workspace diagnostic exports and ingestion charges.

Mock-provider tests check public/private plans and reject absent private
subnets without Azure credentials. Hook tests check image synchronization,
preserved refresh identity/settings and rejected unsafe image references.
They do **not** prove regional availability, real ARM acceptance, RBAC
propagation, DINE operation, DNS reachability or live application health.
The explicit RBAC propagation delay is practical ordering, not a guarantee.
No live Azure deployment or application container runtime validation is claimed
by the mocked tests. After deployment, run `scripts/smoke-auth.sh SERVICE_WEB_URI`
and verify a scheduled refresh execution. A full scenario smoke additionally
requires an interactively acquired delegated token; CI OIDC cannot act as a user.

Review cleanup plans carefully: the shared resource group, network/DNS and
remote state store must not be deleted with app-owned resources.

References: [azd hooks](https://learn.microsoft.com/azure/developer/azure-developer-cli/azd-extensibility),
[Maps metrics](https://learn.microsoft.com/azure/azure-monitor/reference/supported-metrics/microsoft-maps-accounts-metrics),
[Cosmos data RBAC](https://learn.microsoft.com/azure/cosmos-db/nosql/how-to-connect-role-based-access-control),
[AzureRM](https://registry.terraform.io/providers/hashicorp/azurerm/latest),
[AzureCAF](https://registry.terraform.io/providers/aztfmod/azurecaf/latest),
[Time](https://registry.terraform.io/providers/hashicorp/time/latest).
