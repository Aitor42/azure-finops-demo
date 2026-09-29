terraform {
  # azurerm 4.x needs Terraform 1.8+ (provider-defined functions).
  required_version = ">= 1.8.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
    time = {
      source  = "hashicorp/time"
      version = "~> 0.12"
    }
    external = {
      source  = "hashicorp/external"
      version = "~> 2.3"
    }
  }

  # The remote state backend lives in backend.tf (partial config).
}

provider "azurerm" {
  features {}
}

# Identity running terraform (your user or a service principal).
# Used for the Key Vault tenant_id and the cost export subscription_id.
data "azurerm_client_config" "current" {}

# Random suffix for names that must be globally unique (storage, key vault).
resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}
