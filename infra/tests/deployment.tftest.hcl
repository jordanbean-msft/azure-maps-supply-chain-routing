mock_provider "azurerm" {
  mock_data "azurerm_resource_group" {
    defaults = {
      name     = "existing-demo-rg"
      location = "eastus2"
      id       = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/existing-demo-rg"
    }
  }
  mock_data "azurerm_client_config" {
    defaults = {
      subscription_id = "00000000-0000-0000-0000-000000000001"
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
      id             = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/existing-demo-rg/providers/Microsoft.App/managedEnvironments/mockresource"
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
mock_provider "azuread" {
  mock_resource "azuread_application_registration" {
    override_during = plan
    defaults = {
      id        = "/applications/00000000-0000-0000-0000-000000000004"
      object_id = "00000000-0000-0000-0000-000000000004"
      client_id = "00000000-0000-0000-0000-000000000005"
    }
  }
}

variables {
  azure = {
    subscription_id     = "00000000-0000-0000-0000-000000000001"
    tenant_id           = "00000000-0000-0000-0000-000000000002"
    principal_id        = "00000000-0000-0000-0000-000000000003"
    location            = "eastus2"
    environment_name    = "test"
    resource_group_name = "existing-demo-rg"
  }
  naming         = jsondecode(file("main.tfvars.json")).naming
  monitoring     = jsondecode(file("main.tfvars.json")).monitoring
  registry       = jsondecode(file("main.tfvars.json")).registry
  cosmos         = jsondecode(file("main.tfvars.json")).cosmos
  maps           = jsondecode(file("main.tfvars.json")).maps
  workloads      = jsondecode(file("main.tfvars.json")).workloads
  authentication = jsondecode(file("main.tfvars.json")).authentication
}

run "public_demo" {
  command = plan
  variables {
    public_network_access_enabled = true
    network = {
      infrastructure_subnet_id   = ""
      private_endpoint_subnet_id = ""
    }
  }
  assert {
    condition     = output.SERVICE_WEB_URI == "https://mockresource.test.azurecontainerapps.io"
    error_message = "The web service must expose the expected browser origin."
  }
  assert {
    condition     = output.COSMOS_CONTAINER == "scenarios"
    error_message = "Backend persistence must use the provisioned scenario container."
  }
  assert {
    condition = (
      output.ENTRA_CLIENT_ID == "00000000-0000-0000-0000-000000000005" &&
      output.ENTRA_TENANT_ID == var.azure.tenant_id &&
      output.ENTRA_API_SCOPE == "api://${var.azure.tenant_id}/scroute-${local.resource_token}/access_as_user"
    )
    error_message = "Deployment must export the same public tenant, SPA/API client and delegated scope supplied to the API."
  }
  assert {
    condition = (
      azuread_application_redirect_uris.spa.type == "SPA" &&
      azuread_application_redirect_uris.spa.redirect_uris == toset(["${output.SERVICE_WEB_URI}/"])
    )
    error_message = "Only the production root may be a SPA sign-in/post-logout redirect by default; no localhost is automatic."
  }
}

run "private_existing_subnets" {
  command = plan
  variables {
    public_network_access_enabled = false
    network = {
      infrastructure_subnet_id   = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/network/providers/Microsoft.Network/virtualNetworks/existing/subnets/aca"
      private_endpoint_subnet_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/network/providers/Microsoft.Network/virtualNetworks/existing/subnets/endpoints"
    }
  }
  assert {
    condition     = output.SERVICE_API_URI == "https://mockresource.internal.test.azurecontainerapps.io"
    error_message = "API origins must remain environment-internal even with private ingress."
  }
}

run "explicit_development_redirect" {
  command = plan
  variables {
    public_network_access_enabled = true
    network = {
      infrastructure_subnet_id   = ""
      private_endpoint_subnet_id = ""
    }
    authentication = {
      extra_spa_redirect_uris = ["http://localhost:5173/"]
    }
  }
  assert {
    condition     = azuread_application_redirect_uris.spa.redirect_uris == toset(["${output.SERVICE_WEB_URI}/", "http://localhost:5173/"])
    error_message = "Explicit development roots must supplement, not replace, the production sign-in/post-logout root."
  }
}

run "reject_insecure_redirect" {
  command = plan
  variables {
    public_network_access_enabled = true
    network = {
      infrastructure_subnet_id   = ""
      private_endpoint_subnet_id = ""
    }
    authentication = {
      extra_spa_redirect_uris = ["http://untrusted.example/"]
    }
  }
  expect_failures = [var.authentication]
}

run "reject_nonroot_redirect" {
  command = plan
  variables {
    public_network_access_enabled = true
    network = {
      infrastructure_subnet_id   = ""
      private_endpoint_subnet_id = ""
    }
    authentication = {
      extra_spa_redirect_uris = ["https://example.com/callback?redirect=/"]
    }
  }
  expect_failures = [var.authentication]
}

run "reject_missing_private_network" {
  command = plan
  variables {
    public_network_access_enabled = false
    network = {
      infrastructure_subnet_id   = ""
      private_endpoint_subnet_id = ""
    }
  }
  expect_failures = [var.network]
}

run "reject_truncated_refresh_timeout" {
  command = plan
  variables {
    public_network_access_enabled = true
    network = {
      infrastructure_subnet_id   = ""
      private_endpoint_subnet_id = ""
    }
    workloads = merge(jsondecode(file("main.tfvars.json")).workloads, {
      refresh_timeout_seconds = 600
    })
  }
  expect_failures = [var.workloads]
}

run "reject_incompatible_partition" {
  command = plan
  variables {
    public_network_access_enabled = true
    network = {
      infrastructure_subnet_id   = ""
      private_endpoint_subnet_id = ""
    }
    cosmos = merge(jsondecode(file("main.tfvars.json")).cosmos, {
      partition_key_paths = ["/scenarioId"]
    })
  }
  expect_failures = [var.cosmos]
}
