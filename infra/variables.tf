variable "azure" {
  description = "Existing Azure context supplied by azd."
  type = object({
    subscription_id     = string
    tenant_id           = string
    location            = string
    environment_name    = string
    resource_group_name = string
    principal_id        = string
  })
  validation {
    condition     = can(regex("^[a-z0-9]+(-[a-z0-9]+)*$", var.azure.environment_name))
    error_message = "Use lowercase alphanumeric environment names with internal hyphens."
  }
}

variable "naming" {
  description = "Short project identifier for tags."
  type        = object({ project_name = string })
  validation {
    condition     = can(regex("^[a-z0-9]{1,8}$", var.naming.project_name))
    error_message = "project_name must contain 1-8 lowercase alphanumeric characters."
  }
}

variable "public_network_access_enabled" {
  description = "Explicit operator choice: false requires existing private networking; true enables the public demonstration."
  type        = bool
  nullable    = false
}

variable "network" {
  description = "Pre-existing delegated Container Apps and private endpoint subnet IDs; empty strings only in public mode."
  type = object({
    infrastructure_subnet_id   = string
    private_endpoint_subnet_id = string
  })
  validation {
    condition = alltrue([
      for id in [var.network.infrastructure_subnet_id, var.network.private_endpoint_subnet_id] :
      id == "" || can(regex("^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft.Network/virtualNetworks/[^/]+/subnets/[^/]+$", id))
    ])
    error_message = "Subnet IDs must be fully qualified existing Azure subnet IDs, or empty in public mode."
  }
  validation {
    condition     = var.public_network_access_enabled || (var.network.infrastructure_subnet_id != "" && var.network.private_endpoint_subnet_id != "")
    error_message = "Private mode requires both pre-existing delegated ACA and private endpoint subnet IDs."
  }
}

variable "monitoring" {
  description = "Explicit monitoring sizing, retention and telemetry limits."
  type = object({
    workspace_sku           = string
    retention_days          = number
    daily_quota_gb          = number
    application_type        = string
    insights_retention_days = number
    insights_daily_cap_gb   = number
    sampling_percentage     = number
  })
}

variable "registry" {
  description = "ACR SKU; private endpoints require Premium."
  type        = object({ sku = string })
  validation {
    condition     = contains(["Basic", "Standard", "Premium"], var.registry.sku)
    error_message = "registry.sku must be Basic, Standard or Premium."
  }
}

variable "cosmos" {
  description = "Serverless Cosmos NoSQL schema, retention and consistency."
  type = object({
    offer_type                = string
    kind                      = string
    consistency_level         = string
    database_name             = string
    container_name            = string
    partition_key_paths       = list(string)
    partition_key_version     = number
    default_ttl_seconds       = number
    minimal_tls_version       = string
    backup_type               = string
    backup_interval_minutes   = number
    backup_retention_hours    = number
    backup_storage_redundancy = string
  })
  validation {
    condition     = var.cosmos.partition_key_paths == tolist(["/scenario_id"]) && var.cosmos.default_ttl_seconds > 0
    error_message = "Use the scenario_id partition and a positive public-demo document TTL."
  }
}

variable "maps" {
  description = "Azure Maps pricing tier and allowed browser origins; same-origin web hostname is added automatically."
  type = object({
    sku_name              = string
    extra_allowed_origins = list(string)
  })
  validation {
    condition     = var.maps.sku_name == "G2"
    error_message = "Azure Maps must use the Gen2 G2 SKU."
  }
}

variable "workloads" {
  description = "Explicit Container Apps images, resources, scaling, probes, refresh schedule and backend bounds."
  type = object({
    bootstrap_image               = string
    revision_mode                 = string
    workload_profile_name         = string
    workload_profile_type         = string
    transport                     = string
    logs_destination              = string
    api_cpu                       = number
    api_memory                    = string
    api_min_replicas              = number
    api_max_replicas              = number
    api_port                      = number
    web_cpu                       = number
    web_memory                    = string
    web_min_replicas              = number
    web_max_replicas              = number
    web_port                      = number
    http_concurrent_requests      = number
    max_inactive_revisions        = number
    probe_initial_delay_seconds   = number
    probe_interval_seconds        = number
    probe_timeout_seconds         = number
    probe_failure_threshold       = number
    startup_failure_threshold     = number
    readiness_success_threshold   = number
    refresh_cpu                   = number
    refresh_memory                = string
    refresh_cron                  = string
    refresh_timeout_seconds       = number
    refresh_retry_limit           = number
    refresh_parallelism           = number
    refresh_completion_count      = number
    refresh_enabled               = bool
    refresh_max_scenarios         = number
    identity_propagation_duration = string
    app_mode                      = string
    telemetry_enabled             = bool
    backend_env                   = map(string)
  })
  validation {
    condition = (
      var.workloads.api_port == 8000 && var.workloads.web_port == 8080 &&
      var.workloads.api_min_replicas >= 1 &&
      var.workloads.api_max_replicas >= var.workloads.api_min_replicas &&
      var.workloads.web_max_replicas >= var.workloads.web_min_replicas &&
      var.workloads.app_mode == "live" &&
      var.workloads.workload_profile_type == "Consumption" &&
      var.workloads.refresh_max_scenarios > 0 &&
      !endswith(var.workloads.bootstrap_image, ":latest")
    )
    error_message = "Use live mode, Consumption, ports 8000/8080, a warm API, valid replica bounds, bounded refresh and a non-latest bootstrap image."
  }
  validation {
    condition = try(
      tonumber(var.workloads.backend_env["RUN_TIMEOUT_SECONDS"]) > 0 &&
      var.workloads.refresh_timeout_seconds >= var.workloads.refresh_max_scenarios * tonumber(var.workloads.backend_env["RUN_TIMEOUT_SECONDS"]) + 60 &&
      tonumber(var.workloads.backend_env["SNAPSHOT_TTL_SECONDS"]) >= tonumber(var.workloads.backend_env["RUN_TIMEOUT_SECONDS"]) + 60,
      false
    )
    error_message = "Provide positive RUN_TIMEOUT_SECONDS, snapshot TTL >= run timeout +60 seconds, and a refresh timeout covering all sequential scenarios plus 60 seconds."
  }
}

variable "tags" {
  description = "Additional tags; required azd discovery tags cannot be overridden."
  type        = map(string)
  default     = {}
}
