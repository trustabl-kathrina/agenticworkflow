# AgenticWorkflow Makefile
# Common development and deployment commands

.PHONY: help install test lint format build deploy clean local

PROJECT_DIR := $(shell pwd)
SRC_DIR := $(PROJECT_DIR)/src
INFRA_DIR := $(PROJECT_DIR)/infrastructure
ENV := dev
REGION := us-central1
PROJECT_ID := $(shell gcloud config get-value project 2>/dev/null || echo "your-project-id")

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies with uv
	uv sync --all-extras

test: ## Run test suite
	uv run pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	uv run pytest tests/unit -v --tb=short

test-integration: ## Run integration tests only
	uv run pytest tests/integration -v --tb=short

lint: ## Run linter (ruff)
	uv run ruff check src/ tests/

format: ## Format code with ruff
	uv run ruff format src/ tests/

typecheck: ## Run type checker (mypy)
	uv run mypy src/

build: ## Build Docker image
	docker build -t agentic-workflow:latest .

local: ## Run server locally for development
	uv run uvicorn agentic_workflow.api.server:app --reload --host 0.0.0.0 --port 8080

local-docker: ## Run server in Docker locally
	docker run -p 8080:8080 \
		-e GOOGLE_CLOUD_PROJECT=$(PROJECT_ID) \
		-e GOOGLE_CLOUD_LOCATION=$(REGION) \
		-e AGENT_MODEL=gemini-2.5-flash \
		agentic-workflow:latest

tf-init: ## Initialize Terraform
	cd $(INFRA_DIR)/environments/$(ENV) && terraform init

tf-plan: ## Terraform plan
	cd $(INFRA_DIR)/environments/$(ENV) && terraform plan -var-file=terraform.tfvars

tf-apply: ## Terraform apply
	cd $(INFRA_DIR)/environments/$(ENV) && terraform apply -var-file=terraform.tfvars -auto-approve

tf-destroy: ## Terraform destroy (DANGEROUS)
	cd $(INFRA_DIR)/environments/$(ENV) && terraform destroy -var-file=terraform.tfvars -auto-approve

deploy: ## Deploy to Cloud Run via Cloud Build
	gcloud builds submit \
		--project $(PROJECT_ID) \
		--region $(REGION) \
		--tag $(REGION)-docker.pkg.dev/$(PROJECT_ID)/dev-agentic-workflow/agent:$$(git rev-parse --short HEAD)
	gcloud run services update-agent $(shell cd $(INFRA_DIR)/environments/$(ENV) && terraform output -raw agent_service_name 2>/dev/null || echo "agentic-workflow-dev") \
		--image $(REGION)-docker.pkg.dev/$(PROJECT_ID)/dev-agentic-workflow/agent:$$(git rev-parse --short HEAD) \
		--region $(REGION) \
		--project $(PROJECT_ID)

clean: ## Clean build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov dist build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

check: lint typecheck test ## Run all checks

.DEFAULT_GOAL := help
