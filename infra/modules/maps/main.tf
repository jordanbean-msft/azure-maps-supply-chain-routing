resource "azurecaf_name" "maps" {
  name          = var.resource_token
  resource_type = "azurerm_maps_account"
  random_length = 0
  clean_input   = true
}

resource "azurerm_maps_account" "maps" {
  name                         = azurecaf_name.maps.result
  resource_group_name          = var.resource_group_name
  location                     = "global"
  sku_name                     = var.sku_name
  local_authentication_enabled = false
  tags                         = var.tags
  cors {
    allowed_origins = var.allowed_origins
  }
  lifecycle {
    precondition {
      condition     = var.public_network_access_enabled != null && var.location != ""
      error_message = "An explicit shared network posture and deployment location are required; Maps itself uses public global endpoints."
    }
  }
}

resource "azurerm_role_definition" "browser" {
  name = "Maps Browser Render and Traffic ${var.resource_token}"
  # Preserve the deployed ID and assignments while enabling traffic overlays.
  role_definition_id = uuidv5("dns", "${var.resource_group_id}/${var.resource_token}/maps-render-only")
  scope              = var.resource_group_id
  description        = "Render and traffic access for short-lived browser map tokens; no search, route or weather service access."
  assignable_scopes  = [var.resource_group_id]
  permissions {
    actions = []
    data_actions = [
      "Microsoft.Maps/accounts/services/render/read",
      "Microsoft.Maps/accounts/services/traffic/read",
    ]
  }
}
resource "azurerm_role_assignment" "browser" {
  name                             = uuidv5("dns", "${azurerm_maps_account.maps.id}/browser/render-only")
  scope                            = azurerm_maps_account.maps.id
  role_definition_id               = azurerm_role_definition.browser.role_definition_resource_id
  principal_id                     = var.browser_principal_id
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

resource "azurerm_role_assignment" "reader" {
  for_each                         = var.reader_principals
  name                             = uuidv5("dns", "${azurerm_maps_account.maps.id}/${each.key}/Azure Maps Data Reader")
  scope                            = azurerm_maps_account.maps.id
  role_definition_name             = "Azure Maps Data Reader"
  principal_id                     = each.value
  principal_type                   = "ServicePrincipal"
  skip_service_principal_aad_check = true
}

data "azurerm_monitor_diagnostic_categories" "maps" {
  resource_id = azurerm_maps_account.maps.id
}
resource "azurerm_monitor_diagnostic_setting" "maps" {
  name                           = "${azurerm_maps_account.maps.name}-diagnostics"
  target_resource_id             = azurerm_maps_account.maps.id
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  log_analytics_destination_type = "AzureDiagnostics"
  dynamic "enabled_log" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.maps.log_category_types)
    content {
      category = enabled_log.value
    }
  }
  dynamic "enabled_metric" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.maps.metrics)
    content {
      category = enabled_metric.value
    }
  }
}
# Azure Maps does not offer Private Link or native Application Insights agent
# integration. Private workloads still need controlled HTTPS egress to Maps.
