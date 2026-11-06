output "name" {
  description = "Registry name consumed by azd."
  value       = azurerm_container_registry.registry.name
}
output "login_server" {
  description = "Registry endpoint consumed by azd and managed-identity image pulls."
  value       = azurerm_container_registry.registry.login_server
}
output "rbac_ids" {
  description = "Role assignment IDs used to order workload startup."
  value       = concat([for role in azurerm_role_assignment.pull : role.id], [azurerm_role_assignment.push.id])
}
