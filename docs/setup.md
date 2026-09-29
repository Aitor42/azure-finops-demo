# Setup

## Prerequisites

- An Azure account (free-tier subscription with credit works)
- `az` CLI
- Terraform >= 1.8 (azurerm 4.x)
- Docker + Docker Compose
- Python 3.11+ (only for the scripts)

## 0. Register resource providers (first time only)

```bash
az provider register -n Microsoft.Web --wait
az provider register -n Microsoft.Storage --wait
az provider register -n Microsoft.KeyVault --wait
az provider register -n Microsoft.Automation --wait
az provider register -n Microsoft.Insights --wait
az provider register -n Microsoft.CostManagementExports --wait
```

## 1. Deploy the infrastructure

```bash
az login                                   # authenticate (or use a service principal)

cd terraform
cp terraform.tfvars.example terraform.tfvars   # edit your email (budget defaults to 30€/month)

# --- Remote state backend (recommended) ---
bash ../scripts/bootstrap_backend.sh        # creates the tfstate Storage Account
cp backend.hcl.example backend.hcl          # fill in the printed values

terraform init -backend-config=backend.hcl
# If you already have local state, migrate it instead:
#   terraform init -migrate-state -backend-config=backend.hcl

terraform plan
terraform apply
```

> **Remote state:** `backend.tf` declares a partial `azurerm` backend, so
> `terraform init` needs `-backend-config=backend.hcl`. If you prefer to keep
> local state, delete `backend.tf` and run plain `terraform init`. CI runs
> `terraform init -backend=false` so it works without Azure credentials.

> **Role needed:** your identity needs `Contributor` on the subscription to
> create the cost export and the role assignments.

> **Student / Free Trial subscriptions:** Automation Accounts can only be created
> in a subset of regions (`eastus`, `eastus2`, `westus`, `northeurope`,
> `southeastasia`, `japanwest`) and only ONE account per region. The region is
> **picked automatically** at plan time (`dates.tf` →
> `scripts/pick_automation_region.sh`), skipping any region blocked by a
> soft-deleted account.

> **Automation soft-delete gotcha:** a deleted Automation Account soft-deletes for
> 30 days (blocking its region) with no CLI/REST restore (portal only). The
> automatic region picker works around this, but repeated apply → destroy cycles
> still consume the allowed regions one by one.

> **Dates are auto-computed** (`dates.tf`): the cost export starts today, the
> budget runs from the first of the current month, and the scale schedules start
> tomorrow. There are no date variables to edit.

> **AlwaysOn must stay off:** the web app sets `always_on = false`
> (`app-service.tf`) because AlwaysOn is not allowed on the Free (F1) tier —
> with it enabled, the nightly scale-down to Free fails.

### One-time manual step for the Automation Account

For the scale runbook to work, import the **Az.Accounts** and **Az.Websites**
modules into the Automation Account (`aa-finops` → *Modules* → *Browse gallery*).

## 2. Cost dashboard (Grafana)

```bash
cd scripts
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Grant "Cost Management Reader" to your user on the subscription, then run:
AZURE_SUBSCRIPTION_ID=<your-sub-id> python3 cost_exporter.py
```

In another terminal:

```bash
cd grafana
cp .env.example .env        # then set a strong GF_ADMIN_PASSWORD
docker compose up -d
```

Open **http://localhost:3000** and log in with the `GF_ADMIN_PASSWORD` you set
in `grafana/.env` to see the *"FinOps - Azure Costs"* dashboard. The exporter
polls Azure hourly (`COST_EXPORTER_INTERVAL`); Prometheus scrapes it every 5m.

> Note: don't raise `scrape_interval` too much — Prometheus delays the *first*
> scrape of a target by up to the interval, so with a 1h interval the dashboard
> would show no data for up to an hour.

> **Linux host networking:** the stack binds Prometheus and Grafana to
> `127.0.0.1` (loopback) so they're not exposed on the LAN, and Prometheus uses
> `network_mode: host` to scrape the exporter on `localhost:9099`. This requires
> Linux Docker — on Docker Desktop (macOS/Windows) revert to bridge networking
> and expose the ports explicitly.
>
> The exporter also binds to `127.0.0.1` by default (`COST_EXPORTER_BIND`).
>
> **Prometheus history persists** in a named volume (`prometheus-data`), so
> recreating the container keeps its TSDB. Use `docker compose down -v` if you
> want to wipe it.

## 3. Idle resource scanner

```bash
AZURE_SUBSCRIPTION_ID=<your-sub-id> python3 scripts/finops_scan.py
```

Prints a report of orphaned/idle resources across the whole subscription.

## 4. Destroy

```bash
cd terraform
terraform destroy
```

Always destroy the infrastructure when you are done practicing to avoid burning
the free credit.
