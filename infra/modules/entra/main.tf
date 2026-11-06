locals {
  # Tenant-qualified identifiers satisfy Entra URI restrictions without a
  # self-reference to the registration's generated client ID.
  identifier_uri = "api://${var.tenant_id}/scroute-${var.resource_token}"
}

resource "azuread_application_registration" "app" {
  display_name                           = "scroute-${var.resource_token}"
  description                            = "Supply-chain routing SPA and delegated API; signed-in tenant users share demo scenarios."
  sign_in_audience                       = "AzureADMyOrg"
  requested_access_token_version         = 2
  implicit_access_token_issuance_enabled = false
  implicit_id_token_issuance_enabled     = false
}

resource "azuread_application_owner" "deployer" {
  application_id  = azuread_application_registration.app.id
  owner_object_id = var.owner_object_id
}

resource "azuread_application_identifier_uri" "api" {
  application_id = azuread_application_registration.app.id
  identifier_uri = local.identifier_uri
}

resource "azuread_application_permission_scope" "access_as_user" {
  application_id             = azuread_application_registration.app.id
  scope_id                   = uuidv5("url", "${local.identifier_uri}/access_as_user")
  value                      = "access_as_user"
  type                       = "User"
  admin_consent_display_name = "Access supply-chain routing as a user"
  admin_consent_description  = "Use the shared supply-chain routing scenarios on behalf of the signed-in user."
  user_consent_display_name  = "Access supply-chain routing"
  user_consent_description   = "Use the shared supply-chain routing scenarios on your behalf."
}

resource "azuread_service_principal" "app" {
  client_id                    = azuread_application_registration.app.client_id
  owners                       = [var.owner_object_id]
  app_role_assignment_required = false
}

# Entra application registrations are directory objects, not ARM resources:
# Azure Monitor diagnostic settings and Application Insights do not apply.
# User authentication uses PKCE; no credentials or Graph permissions are created.
