resource "azurecaf_name" "cosmos" {
  name          = var.resource_token
  resource_type = "azurerm_cosmosdb_account"
  random_length = 0
  clean_input   = true
}

resource "azurerm_cosmosdb_account" "cosmos" {
  name                          = azurecaf_name.cosmos.result
  resource_group_name           = var.resource_group_name
  location                      = var.location
  offer_type                    = var.config.offer_type
  kind                          = var.config.kind
  minimal_tls_version           = var.config.minimal_tls_version
  local_authentication_enabled  = false
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = var.tags
  capabilities {
    name = "EnableServerless"
  }
  backup {
    type                = var.config.backup_type
    interval_in_minutes = var.config.backup_interval_minutes
    retention_in_hours  = var.config.backup_retention_hours
    storage_redundancy  = var.config.backup_storage_redundancy
  }
  consistency_policy {
    consistency_level = var.config.consistency_level
  }
  geo_location {
    location          = var.location
    failover_priority = 0
  }
  lifecycle {
    precondition {
      condition     = var.public_network_access_enabled || var.private_endpoint_subnet_id != ""
      error_message = "Private Cosmos requires an existing private endpoint subnet."
    }
  }
}

resource "azurerm_cosmosdb_sql_database" "database" {
  name                = var.config.database_name
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.cosmos.name
}
resource "azurerm_cosmosdb_sql_container" "scenarios" {
  name                  = var.config.container_name
  resource_group_name   = var.resource_group_name
  account_name          = azurerm_cosmosdb_account.cosmos.name
  database_name         = azurerm_cosmosdb_sql_database.database.name
  partition_key_paths   = var.config.partition_key_paths
  partition_key_version = var.config.partition_key_version
  default_ttl           = var.config.default_ttl_seconds
}

# Cosmos native data-plane RBAC, not the similarly named ARM account role.
resource "azurerm_cosmosdb_sql_role_assignment" "data" {
  for_each            = var.data_principals
  name                = uuidv5("dns", "${azurerm_cosmosdb_account.cosmos.id}/${each.key}/data-contributor")
  resource_group_name = var.resource_group_name
  account_name        = azurerm_cosmosdb_account.cosmos.name
  role_definition_id  = "${azurerm_cosmosdb_account.cosmos.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002"
  principal_id        = each.value
  scope               = "${azurerm_cosmosdb_account.cosmos.id}/dbs/${azurerm_cosmosdb_sql_database.database.name}/colls/${azurerm_cosmosdb_sql_container.scenarios.name}"
}

resource "azurerm_private_endpoint" "cosmos" {
  count               = var.public_network_access_enabled ? 0 : 1
  name                = "${azurerm_cosmosdb_account.cosmos.name}-pe"
  resource_group_name = var.resource_group_name
  location            = var.location
  subnet_id           = var.private_endpoint_subnet_id
  tags                = var.tags
  private_service_connection {
    name                           = "${azurerm_cosmosdb_account.cosmos.name}-psc"
    private_connection_resource_id = azurerm_cosmosdb_account.cosmos.id
    subresource_names              = ["Sql"]
    is_manual_connection           = false
  }
  lifecycle {
    ignore_changes = [private_dns_zone_group]
  }
}

data "azurerm_monitor_diagnostic_categories" "cosmos" {
  resource_id = azurerm_cosmosdb_account.cosmos.id
}
resource "azurerm_monitor_diagnostic_setting" "cosmos" {
  name                           = "${azurerm_cosmosdb_account.cosmos.name}-diagnostics"
  target_resource_id             = azurerm_cosmosdb_account.cosmos.id
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  log_analytics_destination_type = "Dedicated"
  dynamic "enabled_log" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.cosmos.log_category_types)
    content {
      category = enabled_log.value
    }
  }
  dynamic "enabled_metric" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.cosmos.metrics)
    content {
      category = enabled_metric.value
    }
  }
}
# SQL databases/containers inherit account diagnostics; Cosmos has no native
# Application Insights integration. Its SDK dependencies are traced by the API.
