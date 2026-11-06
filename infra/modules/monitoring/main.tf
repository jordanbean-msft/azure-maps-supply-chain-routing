resource "azurecaf_name" "log_analytics" {
  name          = var.resource_token
  resource_type = "azurerm_log_analytics_workspace"
  random_length = 0
  clean_input   = true
}

resource "azurecaf_name" "app_insights" {
  name          = var.resource_token
  resource_type = "azurerm_application_insights"
  random_length = 0
  clean_input   = true
}

resource "azurerm_log_analytics_workspace" "law" {
  name                           = azurecaf_name.log_analytics.result
  location                       = var.location
  resource_group_name            = var.resource_group_name
  sku                            = var.config.workspace_sku
  retention_in_days              = var.config.retention_days
  daily_quota_gb                 = var.config.daily_quota_gb
  local_authentication_enabled   = false
  internet_ingestion_access_type = var.public_network_access_enabled ? "Enabled" : "Disabled"
  internet_query_access_type     = var.public_network_access_enabled ? "Enabled" : "Disabled"
  tags                           = var.tags
}

resource "azurerm_application_insights" "appinsights" {
  name                       = azurecaf_name.app_insights.result
  location                   = var.location
  resource_group_name        = var.resource_group_name
  application_type           = var.config.application_type
  workspace_id               = azurerm_log_analytics_workspace.law.id
  retention_in_days          = var.config.insights_retention_days
  daily_data_cap_in_gb       = var.config.insights_daily_cap_gb
  sampling_percentage        = var.config.sampling_percentage
  internet_ingestion_enabled = var.public_network_access_enabled
  internet_query_enabled     = var.public_network_access_enabled
  tags                       = var.tags
}

locals {
  diagnostic_targets = {
    workspace = azurerm_log_analytics_workspace.law.id
    insights  = azurerm_application_insights.appinsights.id
  }
}
data "azurerm_monitor_diagnostic_categories" "monitoring" {
  for_each    = local.diagnostic_targets
  resource_id = each.value
}
resource "azurerm_monitor_diagnostic_setting" "monitoring" {
  for_each                       = local.diagnostic_targets
  name                           = "${each.key}-diagnostics"
  target_resource_id             = each.value
  log_analytics_workspace_id     = azurerm_log_analytics_workspace.law.id
  log_analytics_destination_type = "Dedicated"
  dynamic "enabled_log" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.monitoring[each.key].log_category_types)
    content {
      category = enabled_log.value
    }
  }
  dynamic "enabled_metric" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.monitoring[each.key].metrics)
    content {
      category = enabled_metric.value
    }
  }
}

resource "azurecaf_name" "monitor_scope" {
  name          = var.resource_token
  resource_type = "azurerm_monitor_private_link_scope"
  random_length = 0
  clean_input   = true
}
resource "azurerm_monitor_private_link_scope" "monitoring" {
  count                 = var.public_network_access_enabled ? 0 : 1
  name                  = azurecaf_name.monitor_scope.result
  resource_group_name   = var.resource_group_name
  ingestion_access_mode = "PrivateOnly"
  query_access_mode     = "PrivateOnly"
  tags                  = var.tags
}
resource "azurerm_monitor_private_link_scoped_service" "monitoring" {
  for_each            = var.public_network_access_enabled ? {} : local.diagnostic_targets
  name                = each.key
  resource_group_name = var.resource_group_name
  scope_name          = azurerm_monitor_private_link_scope.monitoring[0].name
  linked_resource_id  = each.value
}
resource "azurerm_private_endpoint" "monitoring" {
  count               = var.public_network_access_enabled ? 0 : 1
  name                = "${azurerm_monitor_private_link_scope.monitoring[0].name}-pe"
  resource_group_name = var.resource_group_name
  location            = var.location
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags
  private_service_connection {
    name                           = "${azurerm_monitor_private_link_scope.monitoring[0].name}-psc"
    private_connection_resource_id = azurerm_monitor_private_link_scope.monitoring[0].id
    subresource_names              = ["azuremonitor"]
    is_manual_connection           = false
  }
  lifecycle {
    ignore_changes = [private_dns_zone_group]
    precondition {
      condition     = var.private_endpoint_subnet_id != ""
      error_message = "Private monitoring requires an existing private endpoint subnet."
    }
  }
  depends_on = [azurerm_monitor_private_link_scoped_service.monitoring]
}
# The Private Link Scope and private endpoint have no independent native
# Application Insights integration; telemetry is collected by their linked services.
