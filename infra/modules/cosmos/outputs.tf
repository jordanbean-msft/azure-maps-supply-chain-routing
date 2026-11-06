output "endpoint" {
  description = "Cosmos HTTPS endpoint for managed-identity authentication."
  value       = azurerm_cosmosdb_account.cosmos.endpoint
}
output "name" {
  description = "Cosmos account name."
  value       = azurerm_cosmosdb_account.cosmos.name
}
output "rbac_ids" {
  description = "Data-plane assignment IDs for workload startup ordering."
  value       = [for assignment in azurerm_cosmosdb_sql_role_assignment.data : assignment.id]
}
