resource "azurecaf_name" "registry" {
  name          = var.resource_token
  resource_type = "azurerm_container_registry"
  random_length = 0
  clean_input   = true
}

resource "azurerm_container_registry" "registry" {
  name                          = azurecaf_name.registry.result
  resource_group_name           = var.resource_group_name
  location                      = var.location
  sku                           = var.sku
  admin_enabled                 = false
  anonymous_pull_enabled        = false
  public_network_access_enabled = var.public_network_access_enabled
  role_assignment_mode          = "LegacyRegistryPermissions"
  tags                          = var.tags

  lifecycle {
    precondition {
      condition     = var.public_network_access_enabled || (var.sku == "Premium" && var.private_endpoint_subnet_id != "")
      error_message = "Private ACR requires Premium and an existing private endpoint subnet."
    }
  }
}

resource "azurerm_role_assignment" "pull" {
  for_each                         = var.pull_principals
  name                             = uuidv5("dns", "${azurerm_container_registry.registry.id}/${each.key}/AcrPull")
  scope                            = azurerm_container_registry.registry.id
  role_definition_name             = "AcrPull"
  principal_id                     = each.value
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "push" {
  name                 = uuidv5("dns", "${azurerm_container_registry.registry.id}/${var.deployer_principal_id}/AcrPush")
  scope                = azurerm_container_registry.registry.id
  role_definition_name = "AcrPush"
  principal_id         = var.deployer_principal_id
}

resource "azurerm_private_endpoint" "registry" {
  count               = var.public_network_access_enabled ? 0 : 1
  name                = "${azurerm_container_registry.registry.name}-pe"
  resource_group_name = var.resource_group_name
  location            = var.location
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags
  private_service_connection {
    name                           = "${azurerm_container_registry.registry.name}-psc"
    private_connection_resource_id = azurerm_container_registry.registry.id
    subresource_names              = ["registry"]
    is_manual_connection           = false
  }
  lifecycle {
    ignore_changes = [private_dns_zone_group]
  }
}

data "azurerm_monitor_diagnostic_categories" "registry" {
  resource_id = azurerm_container_registry.registry.id
}
resource "azurerm_monitor_diagnostic_setting" "registry" {
  name                           = "${azurerm_container_registry.registry.name}-diagnostics"
  target_resource_id             = azurerm_container_registry.registry.id
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  log_analytics_destination_type = "Dedicated"
  dynamic "enabled_log" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.registry.log_category_types)
    content {
      category = enabled_log.value
    }
  }
  dynamic "enabled_metric" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.registry.metrics)
    content {
      category = enabled_metric.value
    }
  }
}
# ACR is not an application host and has no native Application Insights agent.
