mock_provider "azuread" {
  mock_resource "azuread_application_registration" {
    override_during = plan
    defaults = {
      id        = "/applications/00000000-0000-0000-0000-000000000004"
      client_id = "00000000-0000-0000-0000-000000000005"
    }
  }
}

run "single_tenant_delegated_registration" {
  command = plan
  module {
    source = "./modules/entra"
  }
  variables {
    resource_token  = "testresource"
    tenant_id       = "00000000-0000-0000-0000-000000000002"
    owner_object_id = "00000000-0000-0000-0000-000000000003"
  }
  assert {
    condition = (
      azuread_application_api_access.profile.application_id == azuread_application_registration.app.id &&
      azuread_application_api_access.profile.api_client_id == "00000003-0000-0000-c000-000000000000" &&
      azuread_application_api_access.profile.scope_ids == toset(["e1fe6dd8-ba31-4d61-89e7-88639da4683d"]) &&
      azuread_application_api_access.profile.role_ids == null
    )
    error_message = "Profile access must request exactly delegated Graph User.Read, without application roles."
  }
  assert {
    condition = (
      azuread_application_registration.app.sign_in_audience == "AzureADMyOrg" &&
      azuread_application_registration.app.requested_access_token_version == 2 &&
      !azuread_application_registration.app.implicit_access_token_issuance_enabled &&
      !azuread_application_registration.app.implicit_id_token_issuance_enabled
    )
    error_message = "The shared secretless SPA/API must accept only tenant v2 tokens, without implicit grants."
  }
  assert {
    condition = (
      azuread_application_permission_scope.access_as_user.type == "User" &&
      azuread_application_permission_scope.access_as_user.value == "access_as_user" &&
      azuread_application_permission_scope.access_as_user.scope_id == uuidv5("url", "api://${var.tenant_id}/scroute-testresource/access_as_user") &&
      output.api_scope == "api://${var.tenant_id}/scroute-testresource/access_as_user"
    )
    error_message = "The delegated User scope must have a stable ID and tenant-qualified full URI."
  }
  assert {
    condition = (
      azuread_application_owner.deployer.owner_object_id == var.owner_object_id &&
      azuread_service_principal.app.owners == toset([var.owner_object_id]) &&
      azuread_service_principal.app.client_id == output.client_id &&
      !azuread_service_principal.app.app_role_assignment_required
    )
    error_message = "The deployer must own both directory objects and all tenant users may share scenarios without individual assignment."
  }
}
