terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "Default GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "billing_account_id" {
  description = "GCP billing account ID"
  type        = string
}

variable "agent_service_name" {
  description = "Cloud Run service name for the agent"
  type        = string
  default     = "agentic-workflow"
}

variable "agent_image" {
  description = "Container image for the agent (e.g., gcr.io/project/agent:tag)"
  type        = string
}

variable "agent_cpu" {
  description = "CPU allocation for agent Cloud Run service"
  type        = string
  default     = "2"
}

variable "agent_memory" {
  description = "Memory allocation for agent Cloud Run service"
  type        = string
  default     = "4Gi"
}

variable "min_instances" {
  description = "Minimum Cloud Run instances (0 for scale-to-zero)"
  type        = number
  default     = 1
}

variable "max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 20
}

variable "budget_amount" {
  description = "Monthly budget cap in EUR"
  type        = number
  default     = 50
}

variable "allowed_ingress" {
  description = "Allowed ingress for Cloud Run"
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

module "apis" {
  source     = "../../modules/apis"
  project_id = var.project_id
  region     = var.region
}

module "artifact_registry" {
  source     = "../../modules/artifact-registry"
  project_id = var.project_id
  region     = var.region
  environment = var.environment
}

module "iam" {
  source      = "../../modules/iam"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
}

module "secret_manager" {
  source      = "../../modules/secret-manager"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
}

module "firestore" {
  source      = "../../modules/firestore"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
}

module "cloud_run" {
  source             = "../../modules/cloud-run"
  project_id         = var.project_id
  region             = var.region
  environment        = var.environment
  agent_service_name = var.agent_service_name
  agent_image        = var.agent_image
  agent_cpu          = var.agent_cpu
  agent_memory       = var.agent_memory
  min_instances      = var.min_instances
  max_instances      = var.max_instances
  allowed_ingress    = var.allowed_ingress
}

module "budget" {
  source            = "../../modules/budget"
  project_id        = var.project_id
  environment       = var.environment
  billing_account_id = var.billing_account_id
  budget_amount     = var.budget_amount
}

module "monitoring" {
  source      = "../../modules/monitoring"
  project_id  = var.project_id
  region      = var.region
  environment = var.environment
}

output "agent_url" {
  description = "URL of the deployed agent Cloud Run service"
  value       = module.cloud_run.agent_url
}

output "agent_service_account" {
  description = "Service account email for the agent"
  value       = module.iam.agent_sa_email
}

output "artifact_registry" {
  description = "Artifact Registry repository URL"
  value       = module.artifact_registry.repository_name
}

output "firestore_database" {
  description = "Firestore database name"
  value       = module.firestore.database_name
}

output "budget_id" {
  description = "GCP Budget ID"
  value       = module.budget.budget_id
}
