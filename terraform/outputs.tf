output "resource_group" {
  description = "Project resource group"
  value       = azurerm_resource_group.rg.name
}

output "web_app_url" {
  description = "Web app URL"
  value       = "https://${azurerm_linux_web_app.app.default_hostname}"
}

output "storage_account" {
  description = "Storage account that receives the cost export"
  value       = azurerm_storage_account.sa.name
}

output "cost_export_container" {
  description = "Container with the cost export"
  value       = azurerm_storage_container.cost_export.name
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = azurerm_key_vault.kv.vault_uri
}
