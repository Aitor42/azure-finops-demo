# TFLint configuration for the Azure FinOps demo.
# Run `tflint --init` once to install the azurerm ruleset plugin, then `tflint`.
plugin "azurerm" {
  enabled = true
  version = "0.32.0"
  source  = "github.com/terraform-linters/tflint-ruleset-azurerm"
}

# This is a disposable demo torn down with `terraform destroy` (to avoid burning
# free credit), so data-loss protection rules don't apply here.
rule "azurerm_resources_missing_prevent_destroy" {
  enabled = false
}

# The workload is an intentionally minimal static site; auto-heal adds nothing
# to the cost-governance story this project demonstrates.
rule "azurerm_app_service_missing_auto_heal_setting" {
  enabled = false
}
