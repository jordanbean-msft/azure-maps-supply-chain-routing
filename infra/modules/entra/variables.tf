variable "resource_token" {
  description = "Deterministic deployment resource token for the shared SPA/API registration."
  type        = string
}

variable "tenant_id" {
  description = "Single Entra tenant UUID; also namespaces the identifier URI."
  type        = string
  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$", var.tenant_id))
    error_message = "tenant_id must be an Entra tenant UUID."
  }
}

variable "owner_object_id" {
  description = "Deployer's Entra object ID, assigned ownership of both application and enterprise service principal."
  type        = string
  validation {
    condition     = can(regex("^[0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}$", var.owner_object_id))
    error_message = "owner_object_id must be an Entra object UUID, not a client ID."
  }
}
