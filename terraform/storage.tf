# Storage Account (Standard LRS). Hosts the container that receives the daily cost
# export from Cost Management.
resource "azurerm_storage_account" "sa" {
  name                     = "st${var.prefix}${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  # Explicit security posture (TLS 1.2+, no anonymous/nested public access).
  min_tls_version                 = "TLS1_2"
  allow_nested_items_to_be_public = false
  tags                            = local.tags
}

resource "azurerm_storage_container" "cost_export" {
  name                  = "cost-export"
  storage_account_id    = azurerm_storage_account.sa.id
  container_access_type = "private"
}
