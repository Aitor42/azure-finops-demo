variable "prefix" {
  description = "Prefix used to name resources (lowercase alphanumeric, 2-10 chars)"
  type        = string
  default     = "finops"

  validation {
    condition     = can(regex("^[a-z][a-z0-9]{1,9}$", var.prefix))
    error_message = "prefix must be 2-10 lowercase alphanumeric characters, starting with a letter."
  }
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "West Europe"
}

variable "cost_center" {
  description = "Value of the mandatory 'costCenter' tag (enforced by Azure Policy)"
  type        = string
  default     = "cloud-demo"

  validation {
    condition     = length(var.cost_center) > 0
    error_message = "cost_center must not be empty."
  }
}

variable "environment" {
  description = "Environment (tag 'environment')"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of: dev, staging, prod."
  }
}

variable "owner" {
  description = "Owner (tag 'owner')"
  type        = string
  default     = "cloud-team"

  validation {
    condition     = length(var.owner) > 0
    error_message = "owner must not be empty."
  }
}

variable "alert_email" {
  description = "Email that receives budget alerts"
  type        = string
  default     = "finops-alerts@example.com"

  validation {
    condition     = can(regex("^[^@]+@[^@]+\\.[^@]+$", var.alert_email))
    error_message = "alert_email must be a valid email address."
  }
}

variable "monthly_budget" {
  description = "Monthly budget in EUR"
  type        = number
  default     = 30

  validation {
    condition     = var.monthly_budget > 0
    error_message = "monthly_budget must be a positive number."
  }
}

variable "enable_automation" {
  description = "Enable Automation Account and nightly scaling runbook. Disable if subscription hit the 1-account-per-region soft-delete quota."
  type        = bool
  default     = true
}
