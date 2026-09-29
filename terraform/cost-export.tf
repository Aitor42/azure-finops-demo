# Daily export of actual cost (ActualCost, MonthToDate) to a Storage container.
# This CSV/JSON is the source for the Grafana dashboard and historical analysis.
resource "azurerm_subscription_cost_management_export" "daily" {
  name                         = "export-${var.prefix}-daily"
  subscription_id              = "/subscriptions/${data.azurerm_client_config.current.subscription_id}"
  recurrence_type              = "Daily"
  recurrence_period_start_date = "${local.today}T00:00:00Z"
  recurrence_period_end_date   = "${local.export_end}T00:00:00Z"

  export_data_storage_location {
    container_id     = "${azurerm_storage_account.sa.id}/blobServices/default/containers/${azurerm_storage_container.cost_export.name}"
    root_folder_path = "/export"
  }

  export_data_options {
    type       = "ActualCost"
    time_frame = "MonthToDate"
  }
}
