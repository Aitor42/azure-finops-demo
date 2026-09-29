# FinOps practices & AZ-900 alignment

## FinOps framework mapping

| FinOps domain | Capability | Implementation in this project |
|---|---|---|
| Understand Cloud Usage & Cost | Cost allocation | Azure Policy (mandatory `costCenter` tag) + tags on every resource |
| Understand Cloud Usage & Cost | Cost reporting | Daily Cost Management export + Grafana dashboard |
| Quantify Business Value | Budgeting & forecasting | Monthly budget with 80/100/110% alerts |
| Optimize Cloud Usage & Cost | Workload optimization | Nightly scale-down of the App Service Plan |
| Optimize Cloud Usage & Cost | Resource utilization / rightsizing | `finops_scan.py` orphan/idle scanner |

## AZ-900 alignment

- **Describe cloud concepts** → pay-as-you-go mindset, cost optimization
- **Core services** → App Service (compute), Storage (storage), Key Vault (security)
- **Governance & management** → Azure Policy, RBAC, resource groups, Cost Management
- **Cost management** → budgets, alerts, tags, exports

## Implemented

- **CI con `terraform fmt` + `validate` + `tflint`** (`.github/workflows/terraform-ci.yml`).
- **Escaneo de seguridad IaC con Trivy** (`.github/workflows/terraform-ci.yml` + `.trivyignore`).
- **Infracost en GitHub Actions** para estimar coste en cada PR (`.github/workflows/infracost.yml`).
- **Estado de Terraform remoto** (backend `azurerm`, `terraform/backend.tf` + `scripts/bootstrap_backend.sh`).

## Cost-optimization ideas to extend

- Add the *"Inherit a tag from the resource group"* policy (append) to auto-tag resources.
- Anomaly detection with Azure Cost Management alerts.

## Roadmap

- **AKS + GitOps**: mover la carga a Azure Kubernetes Service gestionado con
  ArgoCD/Flux y añadir cost allocation a nivel de pod (OpenCost/Kubecost) — cierra
  el hueco de Kubernetes que más pide el mercado cloud.
- **Bicep + Landing Zones**: portar el stack de gobierno a una Landing Zone
  empresarial (Cloud Adoption Framework) usando Bicep.
