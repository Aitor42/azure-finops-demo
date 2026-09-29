# Remote state backend (azurerm). Storing state locally risks leaking it and
# prevents team collaboration. This is a *partial* backend configuration: the
# real values come from `backend.hcl` (git-ignored) so no names/secrets are
# hardcoded in the repo.
#
#   1. Create the state Storage Account:  bash scripts/bootstrap_backend.sh
#   2. Copy the values into backend.hcl:   cp backend.hcl.example backend.hcl
#   3. Initialize (migrating local state): terraform init -migrate-state -backend-config=backend.hcl
#
# CI runs `terraform init -backend=false` so it doesn't need Azure credentials.
terraform {
  backend "azurerm" {}
}
