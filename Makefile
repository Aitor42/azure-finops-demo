.DEFAULT_GOAL := help
.PHONY: help lint typecheck test test-cov fmt clean plan deploy destroy grafana-up grafana-down

PATH := $(CURDIR)/scripts/.venv/bin:$(CURDIR)/.venv/bin:$(PATH)
export PATH

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "%-15s %s\n", $$1, $$2}'

# -- Python ----------------------------------------------------------------
lint: ## Lint Python code with ruff
	ruff check scripts/ tests/

typecheck: ## Type-check Python code with mypy
	mypy scripts/ tests/

test: ## Run unit tests
	pytest tests/ -v

test-cov: ## Run tests with coverage report
	pytest tests/ -v --cov=scripts --cov-report=term-missing

fmt: ## Auto-format Python code
	ruff check scripts/ tests/ --fix
	ruff format scripts/ tests/

clean: ## Remove generated artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

# -- Terraform -------------------------------------------------------------
plan: ## Run terraform plan
	cd terraform && terraform plan

deploy: ## Run terraform apply
	cd terraform && terraform apply

destroy: ## Run terraform destroy (careful!)
	cd terraform && terraform destroy

# -- Grafana stack ---------------------------------------------------------
grafana-up: ## Start Prometheus + Grafana (Docker)
	cd grafana && docker compose up -d

grafana-down: ## Stop Prometheus + Grafana
	cd grafana && docker compose down
