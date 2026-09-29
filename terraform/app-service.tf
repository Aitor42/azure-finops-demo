# App Service Plan (Linux, B1). The Automation Runbook scales it down to Free at night
# (see automation.tf) — FinOps "workload optimization" practice.
resource "azurerm_service_plan" "app" {
  name                = "asp-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  os_type             = "Linux"
  sku_name            = "B1"
  tags                = local.tags
}

# Packs the static app (../app) into a zip to deploy it with the Web App.
data "archive_file" "app" {
  type        = "zip"
  source_dir  = "${path.module}/../app"
  output_path = "${path.module}/.terraform/app.zip"
}

# The app is intentionally minimal: the focus of the project is governance and
# cost, not business logic.
resource "azurerm_linux_web_app" "app" {
  name                = "app-${var.prefix}"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  service_plan_id     = azurerm_service_plan.app.id
  # Force HTTPS; Azure App Service allows plain HTTP otherwise.
  https_only = true

  app_settings = {
    "COST_CENTER" = var.cost_center
  }

  site_config {
    # No specific runtime: serves static content (the app is minimal).
    http2_enabled = true

    # AlwaysOn keeps the app warm 24/7 but is NOT allowed on the Free (F1) tier.
    # The nightly scale-down to Free (automation.tf) would fail with it enabled,
    # so it must stay off.
    always_on = false
  }

  zip_deploy_file = data.archive_file.app.output_path

  tags = local.tags
}
