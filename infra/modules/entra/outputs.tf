output "application_id" {
  description = "Application resource ID for independently managed hostname-dependent SPA redirects."
  value       = azuread_application_registration.app.id
}

output "client_id" {
  description = "Public client ID shared by the SPA and delegated API."
  value       = azuread_application_registration.app.client_id
}

output "api_scope" {
  description = "Full user-delegated access scope."
  value       = "${azuread_application_identifier_uri.api.identifier_uri}/${azuread_application_permission_scope.access_as_user.value}"
}
