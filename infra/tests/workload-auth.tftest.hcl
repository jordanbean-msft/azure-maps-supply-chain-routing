mock_provider "azurerm" {
  mock_resource "azurerm_maps_account" {
    override_during = plan
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/test/providers/Microsoft.Maps/accounts/test"
    }
  }
  mock_data "azurerm_monitor_diagnostic_categories" {
    defaults = {
      log_category_types = ["Audit"]
      metrics            = ["AllMetrics"]
    }
  }
  mock_resource "azurerm_container_app_environment" {
    override_during = plan
    defaults = {
      default_domain = "test.azurecontainerapps.io"
      id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/test/providers/Microsoft.App/managedEnvironments/test"
    }
  }
}
mock_provider "azurecaf" {
  mock_resource "azurecaf_name" {
    override_during = plan
    defaults = {
      result = "mockresource"
    }
  }
}
mock_provider "time" {}

run "browser_can_render_traffic_without_routing_or_weather_privileges" {
  command = plan
  module {
    source = "./modules/maps"
  }
  variables {
    resource_token                = "testresource"
    resource_group_name           = "test"
    resource_group_id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/test"
    location                      = "eastus2"
    tags                          = {}
    public_network_access_enabled = true
    log_analytics_workspace_id    = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/test/providers/Microsoft.OperationalInsights/workspaces/test"
    sku_name                      = "G2"
    allowed_origins               = ["https://demo.example.com"]
    reader_principals             = {}
    browser_principal_id          = "00000000-0000-0000-0000-000000000004"
  }
  assert {
    condition = (
      length(azurerm_role_definition.browser.permissions[0].actions) == 0 &&
      toset(azurerm_role_definition.browser.permissions[0].data_actions) == toset([
        "Microsoft.Maps/accounts/services/render/read",
        "Microsoft.Maps/accounts/services/traffic/read",
      ]) &&
      azurerm_role_assignment.browser.scope == azurerm_maps_account.maps.id &&
      azurerm_role_assignment.browser.principal_id == var.browser_principal_id
    )
    error_message = "Browser overlays need render and traffic reads on this Maps account only, without management, search, route or weather service permissions."
  }
}

run "protected_api_preserves_workload_boundaries" {
  command = plan
  module {
    source = "./modules/workloads"
  }
  variables {
    resource_token                = "testresource"
    resource_group_name           = "test"
    location                      = "eastus2"
    tags                          = {}
    public_network_access_enabled = true
    infrastructure_subnet_id      = ""
    log_analytics_workspace_id    = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/test/providers/Microsoft.OperationalInsights/workspaces/test"
    appinsights_connection_string = "InstrumentationKey=00000000-0000-0000-0000-000000000006"
    registry_endpoint             = "test.azurecr.io"
    identities = {
      for key in ["api", "web", "refresh", "maps-browser"] : key => {
        id           = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/test/providers/Microsoft.ManagedIdentity/userAssignedIdentities/${key}"
        client_id    = "${key}-client"
        principal_id = "${key}-principal"
      }
    }
    maps_client_id        = "maps-account-client"
    cosmos_endpoint       = "https://test.documents.azure.com:443/"
    cosmos_database       = "supply-chain"
    cosmos_container      = "scenarios"
    extra_allowed_origins = []
    rbac_dependencies     = []
    authentication = {
      tenant_id = "00000000-0000-0000-0000-000000000002"
      client_id = "00000000-0000-0000-0000-000000000005"
      api_scope = "api://00000000-0000-0000-0000-000000000002/scroute-testresource/access_as_user"
    }
    config = merge(jsondecode(file("main.tfvars.json")).workloads, {
      backend_env = merge(jsondecode(file("main.tfvars.json")).workloads.backend_env, {
        AUTH_ENABLED = "false"
      })
    })
  }
  assert {
    condition = alltrue([
      for env in azurerm_container_app.app["api"].template[0].container[0].env :
      env.value == lookup({
        AUTH_ENABLED           = "true"
        ENTRA_TENANT_ID        = var.authentication.tenant_id
        ENTRA_CLIENT_ID        = var.authentication.client_id
        ENTRA_API_SCOPE        = var.authentication.api_scope
        AZURE_CLIENT_ID        = var.identities.api.client_id
        MAPS_BROWSER_CLIENT_ID = var.identities["maps-browser"].client_id
      }, env.name, env.value)
    ])
    error_message = "API authentication must be enabled even if generic backend settings attempt to disable it; workload and Maps identities must remain distinct."
  }
  assert {
    condition = (
      alltrue([for name in ["AUTH_ENABLED", "ENTRA_TENANT_ID", "ENTRA_CLIENT_ID", "ENTRA_API_SCOPE"] :
        contains([for env in azurerm_container_app.app["api"].template[0].container[0].env : env.name], name)
      ]) &&
      !azurerm_container_app.app["api"].ingress[0].external_enabled &&
      azurerm_container_app.app["api"].template[0].min_replicas == var.config.api_min_replicas &&
      azurerm_container_app.app["api"].template[0].max_replicas == var.config.api_max_replicas
    )
    error_message = "The API must receive discovery/token-validation settings without changing internal ingress or replica bounds."
  }
  assert {
    condition = (
      !contains(keys(local.app_config.web.env), "ENTRA_CLIENT_ID") &&
      local.app_config.api.env.MAPS_ALLOWED_ORIGINS == jsonencode(["https://mockresource.test.azurecontainerapps.io"]) &&
      azurerm_container_app.app["api"].identity[0].identity_ids == toset([var.identities.api.id, var.identities["maps-browser"].id]) &&
      azurerm_container_app_job.refresh.identity[0].identity_ids == toset([var.identities.refresh.id]) &&
      azurerm_container_app_job.refresh.template[0].container[0].command == tolist(["python", "-m", "template_repository.refresh"])
    )
    error_message = "Discovery must not require frontend build substitution or change browser Maps CORS/identities or the non-HTTP refresh entry point."
  }
}
