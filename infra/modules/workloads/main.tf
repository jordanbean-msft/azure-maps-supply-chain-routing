resource "azurecaf_name" "environment" {
  name          = var.resource_token
  resource_type = "azurerm_container_app_environment"
  random_length = 0
  clean_input   = true
}
resource "azurecaf_name" "app" {
  for_each      = toset(["api", "web"])
  name          = var.resource_token
  resource_type = "azurerm_container_app"
  suffixes      = [each.key]
  random_length = 0
  clean_input   = true
}
resource "azurecaf_name" "refresh" {
  name = var.resource_token
  # azurecaf has no job naming rule; jobs share Container Apps naming constraints.
  resource_type = "azurerm_container_app"
  suffixes      = ["refresh"]
  random_length = 0
  clean_input   = true
}

resource "azurerm_container_app_environment" "environment" {
  name                                        = azurecaf_name.environment.result
  resource_group_name                         = var.resource_group_name
  location                                    = var.location
  logs_destination                            = var.config.logs_destination
  dapr_application_insights_connection_string = var.appinsights_connection_string
  infrastructure_subnet_id                    = var.infrastructure_subnet_id == "" ? null : var.infrastructure_subnet_id
  internal_load_balancer_enabled              = var.infrastructure_subnet_id == "" ? null : !var.public_network_access_enabled
  public_network_access                       = var.public_network_access_enabled ? "Enabled" : "Disabled"
  tags                                        = var.tags
  workload_profile {
    name                  = var.config.workload_profile_name
    workload_profile_type = var.config.workload_profile_type
  }
  lifecycle {
    precondition {
      condition     = var.public_network_access_enabled || var.infrastructure_subnet_id != ""
      error_message = "Private Container Apps requires an existing delegated infrastructure subnet."
    }
  }
}

locals {
  # Names plus environment domain avoid a cycle between Maps CORS, RBAC and app
  # startup. Internal app origins use the environment's internal DNS convention.
  web_fqdn = "${azurecaf_name.app["web"].result}.${azurerm_container_app_environment.environment.default_domain}"
  api_fqdn = "${azurecaf_name.app["api"].result}.internal.${azurerm_container_app_environment.environment.default_domain}"
  backend_env = merge(var.config.backend_env, {
    APP_MODE              = var.config.app_mode
    AZURE_MAPS_CLIENT_ID  = var.maps_client_id
    COSMOS_ENDPOINT       = var.cosmos_endpoint
    COSMOS_DATABASE       = var.cosmos_database
    COSMOS_CONTAINER      = var.cosmos_container
    MAPS_ALLOWED_ORIGINS  = jsonencode(concat(["https://${local.web_fqdn}"], var.extra_allowed_origins))
    TELEMETRY_ENABLED     = tostring(var.config.telemetry_enabled)
    REFRESH_MAX_SCENARIOS = tostring(var.config.refresh_max_scenarios)
  })
  app_config = {
    api = {
      cpu          = var.config.api_cpu, memory = var.config.api_memory,
      min_replicas = var.config.api_min_replicas, max_replicas = var.config.api_max_replicas,
      port         = var.config.api_port, external = false,
      env = merge(local.backend_env, {
        AZURE_CLIENT_ID        = var.identities["api"].client_id
        MAPS_BROWSER_CLIENT_ID = var.identities["maps-browser"].client_id
      })
    }
    web = {
      cpu          = var.config.web_cpu, memory = var.config.web_memory,
      min_replicas = var.config.web_min_replicas, max_replicas = var.config.web_max_replicas,
      port         = var.config.web_port, external = true,
      env = {
        API_INTERNAL_URL = "https://${local.api_fqdn}"
        AZURE_CLIENT_ID  = var.identities["web"].client_id
      }
    }
  }
}

resource "time_sleep" "rbac" {
  create_duration = var.config.identity_propagation_duration
  triggers = {
    assignments = sha256(jsonencode(var.rbac_dependencies))
    principals  = sha256(jsonencode({ for key, identity in var.identities : key => identity.principal_id }))
  }
}

resource "azurerm_container_app" "app" {
  for_each                     = local.app_config
  name                         = azurecaf_name.app[each.key].result
  resource_group_name          = var.resource_group_name
  container_app_environment_id = azurerm_container_app_environment.environment.id
  workload_profile_name        = var.config.workload_profile_name
  revision_mode                = var.config.revision_mode
  max_inactive_revisions       = var.config.max_inactive_revisions
  tags                         = merge(var.tags, { "azd-service-name" = each.key })
  identity {
    type         = "UserAssigned"
    identity_ids = each.key == "api" ? [var.identities["api"].id, var.identities["maps-browser"].id] : [var.identities[each.key].id]
  }
  registry {
    server   = var.registry_endpoint
    identity = var.identities[each.key].id
  }
  dynamic "secret" {
    for_each = each.key == "api" ? [true] : []
    content {
      name  = "appinsights-connection-string"
      value = var.appinsights_connection_string
    }
  }
  ingress {
    external_enabled           = each.value.external
    allow_insecure_connections = false
    target_port                = each.value.port
    transport                  = var.config.transport
    traffic_weight {
      latest_revision = true
      percentage      = 100
    }
  }
  template {
    min_replicas = each.value.min_replicas
    max_replicas = each.value.max_replicas
    http_scale_rule {
      name                = "http"
      concurrent_requests = tostring(var.config.http_concurrent_requests)
    }
    container {
      name  = each.key
      image = var.config.bootstrap_image
      command = [
        "python", "-c",
        "from http.server import BaseHTTPRequestHandler,HTTPServer; import os; H=type('Bootstrap',(BaseHTTPRequestHandler,),{'do_GET':lambda s:(s.send_response(200),s.end_headers(),s.wfile.write(b'Bootstrap only: run azd deploy'))}); HTTPServer(('0.0.0.0',int(os.environ['PORT'])),H).serve_forever()"
      ]
      cpu    = each.value.cpu
      memory = each.value.memory
      env {
        name  = "PORT"
        value = tostring(each.value.port)
      }
      dynamic "env" {
        for_each = each.value.env
        content {
          name  = env.key
          value = env.value
        }
      }
      dynamic "env" {
        for_each = each.key == "api" ? [true] : []
        content {
          name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
          secret_name = "appinsights-connection-string"
        }
      }
      startup_probe {
        transport               = "TCP"
        port                    = each.value.port
        initial_delay           = var.config.probe_initial_delay_seconds
        interval_seconds        = var.config.probe_interval_seconds
        timeout                 = var.config.probe_timeout_seconds
        failure_count_threshold = var.config.startup_failure_threshold
      }
      liveness_probe {
        transport               = "HTTP"
        port                    = each.value.port
        path                    = each.key == "api" ? "/health/live" : "/"
        initial_delay           = var.config.probe_initial_delay_seconds
        interval_seconds        = var.config.probe_interval_seconds
        timeout                 = var.config.probe_timeout_seconds
        failure_count_threshold = var.config.probe_failure_threshold
      }
      readiness_probe {
        transport               = "HTTP"
        port                    = each.value.port
        path                    = each.key == "api" ? "/health/ready" : "/"
        interval_seconds        = var.config.probe_interval_seconds
        timeout                 = var.config.probe_timeout_seconds
        failure_count_threshold = var.config.probe_failure_threshold
        success_count_threshold = var.config.readiness_success_threshold
      }
    }
  }
  lifecycle {
    # azd owns image deployments, Terraform owns all other application settings.
    ignore_changes = [template[0].container[0].image, template[0].container[0].command]
  }
  depends_on = [time_sleep.rbac]
}

resource "azurerm_container_app_job" "refresh" {
  name                         = azurecaf_name.refresh.result
  resource_group_name          = var.resource_group_name
  location                     = var.location
  container_app_environment_id = azurerm_container_app_environment.environment.id
  workload_profile_name        = var.config.workload_profile_name
  replica_timeout_in_seconds   = var.config.refresh_timeout_seconds
  replica_retry_limit          = var.config.refresh_retry_limit
  tags                         = var.tags
  identity {
    type         = "UserAssigned"
    identity_ids = [var.identities["refresh"].id]
  }
  registry {
    server   = var.registry_endpoint
    identity = var.identities["refresh"].id
  }
  secret {
    name  = "appinsights-connection-string"
    value = var.appinsights_connection_string
  }
  schedule_trigger_config {
    cron_expression          = var.config.refresh_cron
    parallelism              = var.config.refresh_parallelism
    replica_completion_count = var.config.refresh_completion_count
  }
  template {
    container {
      name    = "refresh"
      image   = var.config.bootstrap_image
      command = ["python", "-m", "template_repository.refresh"]
      cpu     = var.config.refresh_cpu
      memory  = var.config.refresh_memory
      dynamic "env" {
        for_each = merge(local.backend_env, {
          AZURE_CLIENT_ID = var.identities["refresh"].client_id
          REFRESH_ENABLED = tostring(var.config.refresh_enabled)
        })
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-connection-string"
      }
    }
  }
  lifecycle {
    # The API postdeploy hook pins this to the deployed API's exact image.
    ignore_changes = [template[0].container[0].image]
  }
  depends_on = [time_sleep.rbac]
}

locals {
  diagnostic_targets = merge(
    { environment = azurerm_container_app_environment.environment.id, refresh = azurerm_container_app_job.refresh.id },
    { for key, app in azurerm_container_app.app : key => app.id }
  )
}
data "azurerm_monitor_diagnostic_categories" "workload" {
  for_each    = local.diagnostic_targets
  resource_id = each.value
}
resource "azurerm_monitor_diagnostic_setting" "workload" {
  for_each                       = local.diagnostic_targets
  name                           = "${each.key}-diagnostics"
  target_resource_id             = each.value
  log_analytics_workspace_id     = var.log_analytics_workspace_id
  log_analytics_destination_type = each.key == "environment" ? "Dedicated" : "AzureDiagnostics"
  dynamic "enabled_log" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.workload[each.key].log_category_types)
    content {
      category = enabled_log.value
    }
  }
  dynamic "enabled_metric" {
    for_each = toset(data.azurerm_monitor_diagnostic_categories.workload[each.key].metrics)
    content {
      category = enabled_metric.value
    }
  }
}
# ACA has no Python auto-instrumentation agent setting: the API and refresh
# process initialize the Azure Monitor OpenTelemetry exporter via the standard
# APPLICATIONINSIGHTS_CONNECTION_STRING. Nginx emits console/access logs to LAW.
