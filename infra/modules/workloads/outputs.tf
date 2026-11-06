output "environment_id" {
  description = "Container Apps environment resource ID."
  value       = azurerm_container_app_environment.environment.id
}
output "environment_name" {
  description = "Container Apps environment name."
  value       = azurerm_container_app_environment.environment.name
}
output "api_name" {
  description = "API Container App name."
  value       = azurerm_container_app.app["api"].name
}
output "web_name" {
  description = "Web Container App name."
  value       = azurerm_container_app.app["web"].name
}
output "refresh_job_name" {
  description = "Scheduled refresh job name."
  value       = azurerm_container_app_job.refresh.name
}
output "web_fqdn" {
  description = "Deterministic web hostname, independently computable before app creation."
  value       = local.web_fqdn
}
output "api_uri" {
  description = "Internal API origin without a trailing slash."
  value       = "https://${local.api_fqdn}"
  sensitive   = true
}
