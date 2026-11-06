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

variables {
  azure = {
    subscription_id     = "00000000-0000-0000-0000-000000000001"
    tenant_id           = "00000000-0000-0000-0000-000000000002"
    principal_id        = "00000000-0000-0000-0000-000000000003"
    location            = "eastus2"
    environment_name    = "test"
    resource_group_name = "existing-demo-rg"
  }
  naming     = jsondecode(file("main.tfvars.json")).naming
  monitoring = jsondecode(file("main.tfvars.json")).monitoring
  registry   = jsondecode(file("main.tfvars.json")).registry
  cosmos     = jsondecode(file("main.tfvars.json")).cosmos
  maps       = jsondecode(file("main.tfvars.json")).maps
  workloads  = jsondecode(file("main.tfvars.json")).workloads
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
