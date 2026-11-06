output "client_id" {
  description = "Maps account x-ms-client-id, not a managed identity client ID."
  value       = azurerm_maps_account.maps.x_ms_client_id
}
output "name" {
  description = "Azure Maps account name."
  value       = azurerm_maps_account.maps.name
}
output "rbac_ids" {
  description = "Maps role assignment IDs for workload startup ordering."
  value       = concat([for role in azurerm_role_assignment.reader : role.id], [azurerm_role_assignment.browser.id])
}
