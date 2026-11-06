output "AZURE_RESOURCE_GROUP" {
  description = "Pre-existing deployment resource group."
  value       = data.azurerm_resource_group.rg.name
}
output "AZURE_CONTAINER_REGISTRY" {
  description = "Canonical azd container registry name."
  value       = module.registry.name
}
output "AZURE_CONTAINER_REGISTRY_ENDPOINT" {
  description = "Canonical azd registry login server."
  value       = module.registry.login_server
}
output "AZURE_CONTAINER_APPS_ENVIRONMENT_ID" {
  description = "Container Apps environment resource ID."
  value       = module.workloads.environment_id
}
output "AZURE_CONTAINER_APPS_ENVIRONMENT_NAME" {
  description = "Container Apps environment name."
  value       = module.workloads.environment_name
}
output "AZURE_CONTAINER_APP_API_NAME" {
  description = "API Container App for deployment and refresh image synchronization."
  value       = module.workloads.api_name
}
output "AZURE_CONTAINER_APP_WEB_NAME" {
  description = "Web Container App name."
  value       = module.workloads.web_name
}
output "AZURE_CONTAINER_APP_REFRESH_JOB_NAME" {
  description = "Refresh job updated by the API postdeploy hook."
  value       = module.workloads.refresh_job_name
}
output "SERVICE_API_URI" {
  description = "Internal API origin; not browser accessible."
  value       = module.workloads.api_uri
  sensitive   = true
}
output "SERVICE_WEB_URI" {
  description = "Web service endpoint for browser and smoke tests."
  value       = "https://${module.workloads.web_fqdn}"
  sensitive   = true
}
output "AZURE_MAPS_CLIENT_ID" {
  description = "Azure Maps account client ID."
  value       = module.maps.client_id
}
output "COSMOS_ENDPOINT" {
  description = "Managed-identity Cosmos service endpoint."
  value       = module.cosmos.endpoint
}
output "COSMOS_DATABASE" {
  description = "Cosmos database name."
  value       = var.cosmos.database_name
}
output "COSMOS_CONTAINER" {
  description = "Scenario-scoped Cosmos container name."
  value       = var.cosmos.container_name
}
output "APPLICATIONINSIGHTS_CONNECTION_STRING" {
  description = "Standard Azure Monitor exporter configuration."
  value       = module.monitoring.app_insights_connection_string
  sensitive   = true
}
output "AZURE_LOG_ANALYTICS_WORKSPACE_ID" {
  description = "Shared diagnostic workspace resource ID."
  value       = module.monitoring.log_analytics_workspace_id
}
