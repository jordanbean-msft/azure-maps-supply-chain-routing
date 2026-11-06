variable "resource_token" {
  description = "Deterministic resource naming token."
  type        = string
}
variable "resource_group_name" {
  description = "Existing resource group name."
  type        = string
}
variable "location" {
  description = "Existing resource group location; Azure Maps accounts use global."
  type        = string
}
variable "tags" {
  description = "Shared resource tags."
  type        = map(string)
}
variable "public_network_access_enabled" {
  description = "Shared posture; Maps exposes public Entra-authenticated endpoints and does not support private endpoints."
  type        = bool
}
variable "log_analytics_workspace_id" {
  description = "Shared diagnostics workspace ID."
  type        = string
}
variable "sku_name" {
  description = "Required Azure Maps Gen2 SKU."
  type        = string
}
variable "allowed_origins" {
  description = "Exact browser origins allowed by Azure Maps CORS."
  type        = list(string)
}
variable "reader_principals" {
  description = "API and refresh workload principal IDs."
  type        = map(string)
}
variable "browser_principal_id" {
  description = "Separate managed identity restricted to rendering map tiles and traffic overlays."
  type        = string
}
variable "resource_group_id" {
  description = "Existing resource group ID for the custom role definition's assignable scope."
  type        = string
}
