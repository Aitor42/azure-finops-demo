# ---------------------------------------------------------------------------
# Continuous optimization (FinOps "Workload optimization"):
# an Automation Account with a PowerShell runbook that scales the App Service
# Plan down to Free (F1) outside business hours and back to Basic (B1) in the
# morning. Note: the Automation Account must have the Az.Accounts and Az.Websites
# modules imported (see README).
# ---------------------------------------------------------------------------

resource "azurerm_automation_account" "aa" {
  count = var.enable_automation ? 1 : 0
  name  = "aa-${var.prefix}"
  # Region is picked automatically (dates.tf → pick_automation_region.sh).
  location            = local.automation_location
  resource_group_name = azurerm_resource_group.rg.name
  sku_name            = "Basic"
  tags                = local.tags

  identity {
    type = "SystemAssigned"
  }
}

# The managed identity only needs to scale the App Service Plan, so grant the
# narrowest built-in role ("Web Plan Contributor") scoped to the plan itself
# instead of "Contributor" over the whole resource group.
resource "azurerm_role_assignment" "aa_app_plan_scaler" {
  count                = var.enable_automation ? 1 : 0
  scope                = azurerm_service_plan.app.id
  role_definition_name = "Web Plan Contributor"
  principal_id         = azurerm_automation_account.aa[0].identity[0].principal_id
}

resource "azurerm_automation_runbook" "scale_plan" {
  count                   = var.enable_automation ? 1 : 0
  name                    = "ScaleAppServicePlan"
  location                = local.automation_location
  resource_group_name     = azurerm_resource_group.rg.name
  automation_account_name = azurerm_automation_account.aa[0].name
  log_verbose             = "true"
  log_progress            = "true"
  runbook_type            = "PowerShell"
  tags                    = local.tags

  content = <<-EOT
    param(
        [Parameter(Mandatory=$true)] [string]$resourcegroupname,
        [Parameter(Mandatory=$true)] [string]$appserviceplanname,
        [Parameter(Mandatory=$true)] [ValidateSet("Free","Basic")] [string]$targettier
    )

    Connect-AzAccount -Identity

    if ($targettier -eq "Free") {
        Write-Output "Scaling $appserviceplanname to Free (off-hours)"
        Set-AzAppServicePlan -ResourceGroupName $resourcegroupname -Name $appserviceplanname `
            -Tier "Free" -WorkerSize "Small" -NumberofWorkers 1
    } else {
        Write-Output "Scaling $appserviceplanname to Basic B1 (business hours)"
        Set-AzAppServicePlan -ResourceGroupName $resourcegroupname -Name $appserviceplanname `
            -Tier "Basic" -WorkerSize "Small" -NumberofWorkers 1
    }
  EOT
}

# NOTE: start_time uses +02:00 (CEST). During CET (winter), the FIRST trigger
# fires ±1h off. Subsequent daily recurrences are DST-adjusted by Azure via
# the `timezone` field.
resource "azurerm_automation_schedule" "scale_down" {
  count                   = var.enable_automation ? 1 : 0
  name                    = "scale-down-2000"
  resource_group_name     = azurerm_resource_group.rg.name
  automation_account_name = azurerm_automation_account.aa[0].name
  frequency               = "Day"
  interval                = 1
  timezone                = "Europe/Madrid"
  start_time              = "${local.tomorrow}T20:00:00+02:00"
}

resource "azurerm_automation_schedule" "scale_up" {
  count                   = var.enable_automation ? 1 : 0
  name                    = "scale-up-0800"
  resource_group_name     = azurerm_resource_group.rg.name
  automation_account_name = azurerm_automation_account.aa[0].name
  frequency               = "Day"
  interval                = 1
  timezone                = "Europe/Madrid"
  start_time              = "${local.tomorrow}T08:00:00+02:00"
}

resource "azurerm_automation_job_schedule" "scale_down" {
  count                   = var.enable_automation ? 1 : 0
  resource_group_name     = azurerm_resource_group.rg.name
  automation_account_name = azurerm_automation_account.aa[0].name
  schedule_name           = azurerm_automation_schedule.scale_down[0].name
  runbook_name            = azurerm_automation_runbook.scale_plan[0].name
  parameters = {
    resourcegroupname  = azurerm_resource_group.rg.name
    appserviceplanname = azurerm_service_plan.app.name
    targettier         = "Free"
  }
}

resource "azurerm_automation_job_schedule" "scale_up" {
  count                   = var.enable_automation ? 1 : 0
  resource_group_name     = azurerm_resource_group.rg.name
  automation_account_name = azurerm_automation_account.aa[0].name
  schedule_name           = azurerm_automation_schedule.scale_up[0].name
  runbook_name            = azurerm_automation_runbook.scale_plan[0].name
  parameters = {
    resourcegroupname  = azurerm_resource_group.rg.name
    appserviceplanname = azurerm_service_plan.app.name
    targettier         = "Basic"
  }
}
