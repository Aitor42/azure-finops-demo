#!/usr/bin/env bash
# One-time bootstrap for the remote Terraform state backend.
# Creates a Storage Account + container to hold terraform.tfstate, then prints
# the values to paste into terraform/backend.hcl (see backend.hcl.example).
#
# Usage:  bash scripts/bootstrap_backend.sh
set -euo pipefail

RESOURCE_GROUP="${TFSTATE_RG:-rg-tfstate}"
LOCATION="${LOCATION:-westeurope}"
CONTAINER_NAME="tfstate"
KEY="finops-demo.tfstate"

# Storage account names must be 3-24 lowercase alphanumeric characters.
STORAGE_ACCOUNT="sttfstate$(openssl rand -hex 3)"

echo "Creating state backend ($RESOURCE_GROUP / $STORAGE_ACCOUNT)..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none
az storage account create \
  --name "$STORAGE_ACCOUNT" \
  --resource-group "$RESOURCE_GROUP" \
  --sku Standard_LRS \
  --kind StorageV2 \
  --min-tls-version TLS1_2 \
  --output none
az storage container create \
  --name "$CONTAINER_NAME" \
  --account-name "$STORAGE_ACCOUNT" \
  --auth-mode login \
  --output none

cat <<EOF

State backend ready. Create terraform/backend.hcl with:

resource_group_name  = "$RESOURCE_GROUP"
storage_account_name = "$STORAGE_ACCOUNT"
container_name       = "$CONTAINER_NAME"
key                  = "$KEY"

Then initialize Terraform against it:

  cd terraform
  terraform init -migrate-state -backend-config=backend.hcl
EOF
