# ---------------------------------------------------------------------------
# Time-derived values and self-healing Automation Account region selection.
#
# Everything here is computed so you never hand-edit dates or pick a region:
#   - `time_static` snapshots the first-apply timestamp (stable, no perpetual diffs).
#   - the `external` data source asks Azure which Automation Account regions are
#     actually free right now (Student/Free-Trial subscriptions allow only a few
#     regions AND a soft-deleted account blocks its region for 30 days).
# ---------------------------------------------------------------------------

resource "time_static" "deploy" {}

data "external" "automation_region" {
  program = ["bash", "${path.module}/../scripts/pick_automation_region.sh"]
}

locals {
  # UTC dates derived from the deploy snapshot. These keep the cost export and
  # the budgets valid even if the demo is applied months later.
  today       = formatdate("YYYY-MM-DD", time_static.deploy.rfc3339)
  tomorrow    = formatdate("YYYY-MM-DD", timeadd(time_static.deploy.rfc3339, "24h"))
  month_start = formatdate("YYYY-MM-01", time_static.deploy.rfc3339)
  budget_end  = formatdate("YYYY-MM-01", timeadd(time_static.deploy.rfc3339, "8760h"))
  # 5-year horizon for the cost export; re-apply to extend past this date.
  export_end = formatdate("YYYY-MM-DD", timeadd(time_static.deploy.rfc3339, "43800h"))

  # Automation Account region, chosen automatically (see data source above).
  automation_location = data.external.automation_region.result.region
}
