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
  description = "Shared resource tags."
  type        = map(string)
}
variable "public_network_access_enabled" {
  description = "Explicit Cosmos public endpoint access selection."
  type        = bool
}
variable "private_endpoint_subnet_id" {
  description = "Existing private endpoint subnet; DNS zone groups are policy-managed."
  type        = string
}
variable "log_analytics_workspace_id" {
  description = "Shared diagnostics workspace ID."
  type        = string
}
variable "data_principals" {
  description = "API and refresh principal IDs; the web workload has no database access."
  type        = map(string)
}
variable "config" {
  description = "Explicit serverless database configuration."
  type = object({
    offer_type                = string
    kind                      = string
    consistency_level         = string
    database_name             = string
    container_name            = string
    partition_key_paths       = list(string)
    partition_key_version     = number
    default_ttl_seconds       = number
    minimal_tls_version       = string
    backup_type               = string
    backup_interval_minutes   = number
    backup_retention_hours    = number
    backup_storage_redundancy = string
  })
}
