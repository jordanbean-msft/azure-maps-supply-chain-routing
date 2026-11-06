resource "azurecaf_name" "workload" {
  for_each      = toset(["api", "refresh", "web", "maps-browser"])
  name          = var.resource_token
  resource_type = "azurerm_user_assigned_identity"
  suffixes      = [each.key]
  random_length = 0
  clean_input   = true
}

# Managed identities do not expose Azure Monitor resource diagnostics or native
# Application Insights integration; workload telemetry is configured on compute.
resource "azurerm_user_assigned_identity" "workload" {
  for_each            = azurecaf_name.workload
  name                = each.value.result
  resource_group_name = var.resource_group_name
  location            = var.location
  tags                = var.tags
  lifecycle {
    precondition {
      condition     = var.public_network_access_enabled != null
      error_message = "The shared network posture must be an explicit boolean, even for identities without network endpoints."
    }
  }
}
