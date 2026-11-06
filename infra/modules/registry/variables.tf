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
  description = "Enable public data access only for an explicitly selected demonstration."
  type        = bool
}
variable "private_endpoint_subnet_id" {
  description = "Existing private endpoint subnet; DNS is configured by DINE."
  type        = string
}
variable "log_analytics_workspace_id" {
  description = "Shared diagnostics workspace resource ID."
  type        = string
}
variable "sku" {
  description = "Explicit registry SKU; Premium is required for private endpoints."
  type        = string
}
variable "pull_principals" {
  description = "Workload principal IDs granted image-pull permissions."
  type        = map(string)
}
variable "deployer_principal_id" {
  description = "OIDC deployment principal granted image-push permissions."
  type        = string
}
