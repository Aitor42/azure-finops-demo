# Tags applied to every resource. The `costCenter` tag is the one enforced by the
# Azure Policy (effect=deny), so no resource can be created without it.
locals {
  tags = {
    costCenter  = var.cost_center
    environment = var.environment
    owner       = var.owner
    project     = "finops-demo"
    createdBy   = "terraform"
  }
}
