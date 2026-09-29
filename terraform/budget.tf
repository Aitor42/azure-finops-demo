# Action Group: notification channel (email) for cost alerts.
resource "azurerm_monitor_action_group" "cost" {
  name                = "ag-${var.prefix}-cost"
  resource_group_name = azurerm_resource_group.rg.name
  short_name          = "costalert"

  email_receiver {
    name                    = "finops-owner"
    email_address           = var.alert_email
    use_common_alert_schema = true
  }

  tags = local.tags
}

# Monthly budget at the resource group scope. Fires alerts at 80%, 100% and 110%.
# Maps to the FinOps "Budgeting & forecasting" + "Anomaly management" capabilities.
resource "azurerm_consumption_budget_resource_group" "monthly" {
  name              = "budget-${var.prefix}-monthly"
  resource_group_id = azurerm_resource_group.rg.id

  amount     = var.monthly_budget
  time_grain = "Monthly"

  time_period {
    start_date = "${local.month_start}T00:00:00Z"
    end_date   = "${local.budget_end}T00:00:00Z"
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    contact_groups = [azurerm_monitor_action_group.cost.id]
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThan"
    contact_groups = [azurerm_monitor_action_group.cost.id]
  }

  notification {
    enabled        = true
    threshold      = 110
    operator       = "GreaterThan"
    contact_emails = [var.alert_email]
  }
}
