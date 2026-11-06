variable "resource_token" {
  description = "Token used to generate unique resource names."
  type        = string
}

variable "resource_group_name" {
  description = "Name of the resource group."
  type        = string
}

variable "location" {
  description = "Azure region for resources."
  type        = string
}

variable "tags" {
  description = "Tags to apply to resources."
  type        = map(string)
}

variable "public_network_access_enabled" {
  description = "Explicit public telemetry endpoint choice; private mode deploys an Azure Monitor Private Link Scope."
  type        = bool
}
variable "private_endpoint_subnet_id" {
  description = "Existing subnet for the Azure Monitor private endpoint."
  type        = string
}
variable "config" {
  description = "Explicit workspace and Application Insights sizing."
  type = object({
    workspace_sku           = string
    retention_days          = number
    daily_quota_gb          = number
    application_type        = string
    insights_retention_days = number
    insights_daily_cap_gb   = number
    sampling_percentage     = number
  })
}
