# Key Vault with a sample secret. The access policy is granted to the identity
# running terraform so it can create/read the secret.
resource "azurerm_key_vault" "kv" {
  name                       = "kv-${var.prefix}-${random_string.suffix.result}"
  location                   = azurerm_resource_group.rg.location
  resource_group_name        = azurerm_resource_group.rg.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  tags                       = local.tags

  # NOTE (production hardening): enable `purge_protection_enabled = true` and
  # set `public_network_access_enabled = false` for real workloads. Purge
  # protection is irreversible once enabled, so it's left off for this demo so
  # `terraform destroy` can clean the vault up.

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    # Required by the full apply/destroy cycle: Set (create), Get/List (read),
    # and Delete + Purge + Recover (soft-delete is mandatory on Key Vault, so
    # `terraform destroy` purges the secret and a re-apply after a soft-delete
    # recovers it). Only Backup/Restore are omitted.
    secret_permissions = [
      "Get", "List", "Set", "Delete", "Purge", "Recover",
    ]
  }
}

resource "azurerm_key_vault_secret" "demo" {
  name            = "demo-secret"
  value           = "cost-is-not-optional"
  content_type    = "text/plain"
  expiration_date = "2027-08-01T00:00:00Z"
  key_vault_id    = azurerm_key_vault.kv.id
}
