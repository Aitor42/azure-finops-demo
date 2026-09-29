#!/usr/bin/env bash
# Terraform `external` data source: returns the first Azure Automation Account
# region that is allowed for this subscription AND not currently blocked by a
# soft-deleted account. Prints a single JSON object on stdout, e.g.
# {"region":"eastus2"}. Anything on stderr is ignored by Terraform.
set -euo pipefail

# Allow manual override via env var
if [ -n "${AUTOMATION_REGION:-}" ]; then
  printf '{"region":"%s"}\n' "$AUTOMATION_REGION"
  exit 0
fi

# Regions allowed for Student/Free Trial subscriptions, ordered by current availability.
ALLOWED_REGIONS="southeastasia japanwest eastus eastus2 westus northeurope"
FALLBACK_REGION="southeastasia"

BLOCKED_REGIONS=""
if command -v az >/dev/null 2>&1; then
  SUBSCRIPTION_ID="$(az account show --query id -o tsv 2>/dev/null || true)"
  if [ -n "$SUBSCRIPTION_ID" ]; then
    BLOCKED_REGIONS="$(az rest --method GET \
      --url "https://management.azure.com/subscriptions/${SUBSCRIPTION_ID}/providers/Microsoft.Automation/deletedAutomationAccounts?api-version=2023-05-15-preview" \
      --query "value[].Location || value[].Properties.Location || value[].properties.location" -o tsv 2>/dev/null || true)"
  fi
fi

for region in $ALLOWED_REGIONS; do
  blocked=""
  for b in $BLOCKED_REGIONS; do
    [ "$b" = "$region" ] && blocked=1 && break
  done
  if [ -z "$blocked" ]; then
    printf '{"region":"%s"}\n' "$region"
    exit 0
  fi
done

printf '{"region":"%s"}\n' "$FALLBACK_REGION"
