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
  description = "Shared network posture; user-assigned identities have no network endpoint or diagnostic settings."
  type        = bool
}
