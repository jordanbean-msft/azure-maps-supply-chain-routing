data "azurerm_resource_group" "rg" {
  name = var.azure.resource_group_name
}

data "azurerm_client_config" "current" {}

locals {
  resource_token_sha = base64encode(sha256("${var.azure.location}${data.azurerm_client_config.current.subscription_id}${var.azure.resource_group_name}"))
  resource_token     = substr(join("", regexall("[a-z0-9]", lower(local.resource_token_sha))), 0, 13)

  default_tags = merge(
    {
      project     = var.naming.project_name
      environment = var.azure.environment_name
      managed_by  = "terraform"
    },
    var.tags,
    { "azd-env-name" = var.azure.environment_name }
  )
}

module "monitoring" {
  source = "./modules/monitoring"

  resource_token                = local.resource_token
  resource_group_name           = data.azurerm_resource_group.rg.name
  location                      = data.azurerm_resource_group.rg.location
  tags                          = local.default_tags
  public_network_access_enabled = var.public_network_access_enabled
  private_endpoint_subnet_id    = var.network.private_endpoint_subnet_id
  config                        = var.monitoring
}

module "identity" {
  source = "./modules/identity"

  resource_token                = local.resource_token
  resource_group_name           = data.azurerm_resource_group.rg.name
  location                      = data.azurerm_resource_group.rg.location
  tags                          = local.default_tags
  public_network_access_enabled = var.public_network_access_enabled
}

module "registry" {
  source = "./modules/registry"

  resource_token                = local.resource_token
  resource_group_name           = data.azurerm_resource_group.rg.name
  location                      = data.azurerm_resource_group.rg.location
  tags                          = local.default_tags
  public_network_access_enabled = var.public_network_access_enabled
  private_endpoint_subnet_id    = var.network.private_endpoint_subnet_id
  log_analytics_workspace_id    = module.monitoring.log_analytics_workspace_id
  sku                           = var.registry.sku
  pull_principals               = { for key, id in module.identity.principal_ids : key => id if key != "maps-browser" }
  deployer_principal_id         = var.azure.principal_id
}

module "cosmos" {
  source = "./modules/cosmos"

  resource_token                = local.resource_token
  resource_group_name           = data.azurerm_resource_group.rg.name
  location                      = data.azurerm_resource_group.rg.location
  tags                          = local.default_tags
  public_network_access_enabled = var.public_network_access_enabled
  private_endpoint_subnet_id    = var.network.private_endpoint_subnet_id
  log_analytics_workspace_id    = module.monitoring.log_analytics_workspace_id
  config                        = var.cosmos
  data_principals = {
    api     = module.identity.principal_ids.api
    refresh = module.identity.principal_ids.refresh
  }
}

module "maps" {
  source               = "./modules/maps"
  resource_group_id    = data.azurerm_resource_group.rg.id
  browser_principal_id = module.identity.principal_ids["maps-browser"]

  resource_token                = local.resource_token
  resource_group_name           = data.azurerm_resource_group.rg.name
  location                      = data.azurerm_resource_group.rg.location
  tags                          = local.default_tags
  public_network_access_enabled = var.public_network_access_enabled
  log_analytics_workspace_id    = module.monitoring.log_analytics_workspace_id
  sku_name                      = var.maps.sku_name
  allowed_origins               = concat(["https://${module.workloads.web_fqdn}"], var.maps.extra_allowed_origins)
  reader_principals = {
    api     = module.identity.principal_ids.api
    refresh = module.identity.principal_ids.refresh
  }
}

module "workloads" {
  source = "./modules/workloads"

  resource_token                = local.resource_token
  resource_group_name           = data.azurerm_resource_group.rg.name
  location                      = data.azurerm_resource_group.rg.location
  tags                          = local.default_tags
  public_network_access_enabled = var.public_network_access_enabled
  infrastructure_subnet_id      = var.network.infrastructure_subnet_id
  log_analytics_workspace_id    = module.monitoring.log_analytics_workspace_id
  appinsights_connection_string = module.monitoring.app_insights_connection_string
  registry_endpoint             = module.registry.login_server
  identities                    = module.identity.identities
  maps_client_id                = module.maps.client_id
  cosmos_endpoint               = module.cosmos.endpoint
  cosmos_database               = var.cosmos.database_name
  cosmos_container              = var.cosmos.container_name
  extra_allowed_origins         = var.maps.extra_allowed_origins
  config                        = var.workloads
  rbac_dependencies = [
    module.registry.rbac_ids,
    module.cosmos.rbac_ids,
    module.maps.rbac_ids
  ]
}
