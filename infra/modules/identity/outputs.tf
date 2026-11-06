output "identities" {
  description = "Independent identity resource, principal and client IDs per workload."
  value = {
    for key, identity in azurerm_user_assigned_identity.workload : key => {
      id           = identity.id
      principal_id = identity.principal_id
      client_id    = identity.client_id
    }
  }
}
output "principal_ids" {
  description = "Workload principal IDs for least-privilege RBAC."
  value       = { for key, identity in azurerm_user_assigned_identity.workload : key => identity.principal_id }
}
