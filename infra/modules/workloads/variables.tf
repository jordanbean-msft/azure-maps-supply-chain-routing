variable "resource_token" {
  description = "Deterministic resource naming token."
  type        = string
}
variable "resource_group_name" {
  description = "Existing resource group name."
  type        = string
}
variable "location" {
  description = "Existing resource group location."
  type        = string
}
variable "tags" {
  description = "Shared tags, including azd-env-name."
  type        = map(string)
}
variable "public_network_access_enabled" {
  description = "Expose the environment publicly; the API ingress always remains internal."
  type        = bool
}
variable "infrastructure_subnet_id" {
  description = "Existing Microsoft.App/environments delegated subnet; required in private mode."
  type        = string
}
variable "log_analytics_workspace_id" {
  description = "Shared diagnostics workspace resource ID."
  type        = string
}
variable "appinsights_connection_string" {
  description = "Application Insights exporter connection string."
  type        = string
  sensitive   = true
}
variable "registry_endpoint" {
  description = "ACR login server for managed-identity pulls."
  type        = string
}
variable "identities" {
  description = "Independent api, web and refresh user-assigned identities."
  type = map(object({
    id           = string
    principal_id = string
    client_id    = string
  }))
}
variable "maps_client_id" {
  description = "Azure Maps account x-ms-client-id."
  type        = string
}
variable "cosmos_endpoint" {
  description = "Cosmos HTTPS endpoint."
  type        = string
}
variable "cosmos_database" {
  description = "Cosmos database name."
  type        = string
}
variable "cosmos_container" {
  description = "Scenario-partitioned container name."
  type        = string
}
variable "extra_allowed_origins" {
  description = "Additional explicitly trusted origins for browser-token delivery."
  type        = list(string)
}
variable "rbac_dependencies" {
  description = "Completed role assignments which must propagate before application creation."
  type        = list(list(string))
}
variable "authentication" {
  description = "Public identifiers for single-tenant delegated authentication, independent of workload managed identities."
  type = object({
    tenant_id = string
    client_id = string
    api_scope = string
  })
}
variable "config" {
  description = "Explicit runtime, health, scaling and scheduled job configuration."
  type = object({
    bootstrap_image               = string
    revision_mode                 = string
    workload_profile_name         = string
    workload_profile_type         = string
    transport                     = string
    logs_destination              = string
    api_cpu                       = number
    api_memory                    = string
    api_min_replicas              = number
    api_max_replicas              = number
    api_port                      = number
    web_cpu                       = number
    web_memory                    = string
    web_min_replicas              = number
    web_max_replicas              = number
    web_port                      = number
    http_concurrent_requests      = number
    max_inactive_revisions        = number
    probe_initial_delay_seconds   = number
    probe_interval_seconds        = number
    probe_timeout_seconds         = number
    probe_failure_threshold       = number
    startup_failure_threshold     = number
    readiness_success_threshold   = number
    refresh_cpu                   = number
    refresh_memory                = string
    refresh_cron                  = string
    refresh_timeout_seconds       = number
    refresh_retry_limit           = number
    refresh_parallelism           = number
    refresh_completion_count      = number
    refresh_enabled               = bool
    refresh_max_scenarios         = number
    identity_propagation_duration = string
    app_mode                      = string
    telemetry_enabled             = bool
    backend_env                   = map(string)
  })
}
