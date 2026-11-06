terraform {
  required_version = ">= 1.9"

  required_providers {
    azuread = {
      source  = "hashicorp/azuread"
      version = "~> 3.10"
    }
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 5.13"
    }
    azurecaf = {
      source  = "aztfmod/azurecaf"
      version = "~> 2.0"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.14"
    }
  }

  # Backend configured by azd via infra/provider.conf.json (native Terraform remote state).
  # azd substitutes ${RS_*} and ${AZURE_ENV_NAME} placeholders at provision time.
  # Before running azd provision, set:
  #   azd env set RS_RESOURCE_GROUP <rg>
  #   azd env set RS_STORAGE_ACCOUNT <sa>
  #   azd env set RS_CONTAINER_NAME  <container>
  backend "azurerm" {}
}

provider "azuread" {
  tenant_id = var.azure.tenant_id
}

provider "azurerm" {
  subscription_id                 = var.azure.subscription_id
  tenant_id                       = var.azure.tenant_id
  storage_use_azuread             = true
  resource_provider_registrations = "none"

  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
    resource_group {
      prevent_deletion_if_contains_resources = true
    }
  }
}
