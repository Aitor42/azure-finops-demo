# Custom policy: denies creation/update of any resource in the resource group that
# lacks the `costCenter` tag. This is the basis of "cost allocation" in the FinOps
# framework: without tags there is no way to attribute cost.
resource "azurerm_policy_definition" "require_cost_center" {
  name         = "require-costcenter-tag"
  policy_type  = "Custom"
  mode         = "Indexed"
  display_name = "Require costCenter tag on resources"
  description  = "Denies resources that do not have the 'costCenter' tag defined."

  parameters = jsonencode({
    tagName = {
      type = "String"
      metadata = {
        displayName = "Tag name"
        description = "Name of the required tag"
      }
    }
  })

  policy_rule = jsonencode({
    if = {
      field  = "[concat('tags[', parameters('tagName'), ']')]"
      exists = "false"
    }
    then = {
      effect = "deny"
    }
  })
}

# Assignment at the resource group scope.
resource "azurerm_resource_group_policy_assignment" "require_cost_center" {
  name                 = "require-costcenter-tag"
  resource_group_id    = azurerm_resource_group.rg.id
  policy_definition_id = azurerm_policy_definition.require_cost_center.id

  parameters = jsonencode({
    tagName = { value = "costCenter" }
  })
}
