# AgenticWorkflow - GCP Infrastructure
#
# This Terraform configuration provisions the production infrastructure
# for the agentic workflow platform on Google Cloud Platform.
#
# Usage:
#   cd environments/dev
#   terraform init
#   terraform plan -var-file=terraform.tfvars
#   terraform apply -var-file=terraform.tfvars

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

  # Use GCS for remote state in production
  # backend "gcs" {
  #   bucket = "agentic-workflow-terraform-state"
  #   prefix = "dev/terraform.tfstate"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}

# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------

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
  description = "Environment name (dev, staging, prod)"
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
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
  default     = "1"
}

variable "agent_memory" {
  description = "Memory allocation for agent Cloud Run service"
  type        = string
  default     = "2Gi"
}

variable "min_instances" {
  description = "Minimum Cloud Run instances (0 for scale-to-zero)"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum Cloud Run instances"
  type        = number
  default     = 10
}

variable "budget_amount" {
  description = "Monthly budget cap in USD"
  type        = number
  default     = 50
}

variable "allowed_ingress" {
  description = "Allowed ingress for Cloud Run"
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

# ---------------------------------------------------------------------------
# Enable APIs
# ---------------------------------------------------------------------------

locals {
  required_apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudbuild.googleapis.com",
    "firestore.googleapis.com",
    "pubsub.googleapis.com",
  ]
}

resource "google_project_service" "api" {
  for_each = toset(local.required_apis)
  project  = var.project_id
  service  = each.key

  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Artifact Registry
# ---------------------------------------------------------------------------

resource "google_artifact_registry_repository" "agent_repo" {
  location      = var.region
  project       = var.project_id
  repository_id = "${var.environment}-agentic-workflow"
  description   = "Container images for ${var.environment} agentic workflow"
  format        = "DOCKER"

  depends_on = [google_project_service.api["artifactregistry.googleapis.com"]]
}

# ---------------------------------------------------------------------------
# Service Accounts & IAM
# ---------------------------------------------------------------------------

resource "google_service_account" "agent_sa" {
  project      = var.project_id
  account_id   = "${var.environment}-agent-sa"
  display_name = "Agentic Workflow Agent Service Account (${var.environment})"
}

resource "google_project_iam_member" "agent_aiplatform" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "agent_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "agent_storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "agent_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "agent_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# ---------------------------------------------------------------------------
# Secret Manager
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "api_keys" {
  for_each = toset([
    "gemini-api-key",
    "reddit-client-id",
    "reddit-client-secret",
    "developer-knowledge-key",
  ])

  project   = var.project_id
  secret_id = each.key

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }

  replication {
    automatic = true
  }

  depends_on = [google_project_service.api["secretmanager.googleapis.com"]]
}

# ---------------------------------------------------------------------------
# Firestore (for session state / memory)
# ---------------------------------------------------------------------------

resource "google_firestore_database" "agent_db" {
  project      = var.project_id
  name         = "(default)"
  location_id  = var.region
  type         = "NATIVE"
  delete_protection_enabled = var.environment == "prod"

  depends_on = [google_project_service.api["firestore.googleapis.com"]]
}

# ---------------------------------------------------------------------------
# Cloud Run Service
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "agent" {
  project  = var.project_id
  name     = var.agent_service_name
  location = var.region
  ingress  = var.allowed_ingress

  template {
    service_account = google_service_account.agent_sa.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.agent_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.agent_cpu
          memory = var.agent_memory
        }
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "True"
      }
      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }

      # Inject secrets from Secret Manager
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_keys["gemini-api-key"].secret_id
            version = "latest"
          }
        }
      }

      # Health checks
      startup_probe {
        http_get {
          path = "/health"
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
        }
        period_seconds    = 30
        failure_threshold = 3
      }
    }
  }

  depends_on = [google_project_service.api["run.googleapis.com"]]
}

# Allow public access (IAM authentication via Cloud Run Invoker for production)
resource "google_cloud_run_service_iam_binding" "public" {
  count    = var.environment == "dev" ? 1 : 0
  project  = var.project_id
  location = google_cloud_run_v2_service.agent.location
  service  = google_cloud_run_v2_service.agent.name
  role     = "roles/run.invoker"
  members  = ["allUsers"]
}

# ---------------------------------------------------------------------------
# Budget Alerts & Spend Caps
# ---------------------------------------------------------------------------
# Hard stop at 10 EUR. When spend reaches this cap, eligible services
# (Cloud Run, Vertex AI, etc.) are paused until manually lifted.

resource "google_billing_budget" "agent_budget" {
  billing_account = var.billing_account_id
  display_name    = "${var.environment}-agentic-workflow-budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
    services = [
      "services/run.googleapis.com",
      "services/aiplatform.googleapis.com",
      "services/artifactregistry.googleapis.com",
      "services/secretmanager.googleapis.com",
      "services/firestore.googleapis.com",
      "services/pubsub.googleapis.com",
      "services/monitoring.googleapis.com",
    ]
  }

  amount {
    specified_amount {
      currency_code = "EUR"
      units         = var.budget_amount
    }
  }

  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.8
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }

  all_updates_rule {
    disable_default_iam_recipients = false
  }
}

# ---------------------------------------------------------------------------
# Cloud Monitoring Alerts
# ---------------------------------------------------------------------------

resource "google_monitoring_alert_policy" "agent_errors" {
  project      = var.project_id
  display_name = "${var.environment} - Agent Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Agent 5xx errors"

    condition_threshold {
      filter          = 'resource.type="cloud_run_revision" AND resource.labels.service_name="${google_cloud_run_v2_service.agent.name}" AND metric.type="run.googleapis.com/request_count" AND metric.label.response_code_class="5xx"'
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      aggregations {
        alignment_period    = "60s"
        per_series_aligner  = "ALIGN_RATE"
      }
    }
  }

  notification_channels = []
}

resource "google_monitoring_alert_policy" "agent_latency" {
  project      = var.project_id
  display_name = "${var.environment} - Agent High Latency"
  combiner     = "OR"

  conditions {
    display_name = "Agent p99 latency > 5s"

    condition_threshold {
      filter          = 'resource.type="cloud_run_revision" AND resource.labels.service_name="${google_cloud_run_v2_service.agent.name}" AND metric.type="run.googleapis.com/request_latencies"'
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5000
      aggregations {
        alignment_period    = "300s"
        per_series_aligner  = "ALIGN_PERCENTILE_99"
      }
    }
  }

  notification_channels = []
}

resource "google_monitoring_alert_policy" "budget_burn_rate" {
  project      = var.project_id
  display_name = "${var.environment} - Budget Burn Rate Alert"
  combiner     = "OR"

  conditions {
    display_name = "Daily spend exceeds 3 EUR (30% of 10 EUR budget)"

    condition_threshold {
      filter          = 'resource.type="billing_account" AND metric.type="billing.googleapis.com/budget/burn_rate" AND metric.label.budget_id="${google_billing_budget.agent_budget.budget_id}"'
      duration        = "3600s"
      comparison      = "COMPARISON_GT"
      threshold_value = 3.0
      aggregations {
        alignment_period    = "3600s"
        per_series_aligner  = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = []
}

resource "google_monitoring_alert_policy" "agent_cold_starts" {
  project      = var.project_id
  display_name = "${var.environment} - High Cold Start Rate"
  combiner     = "OR"

  conditions {
    display_name = "Cold starts > 20% of requests"

    condition_threshold {
      filter          = 'resource.type="cloud_run_revision" AND resource.labels.service_name="${google_cloud_run_v2_service.agent.name}" AND metric.type="run.googleapis.com/container/cold_start_count"'
      duration        = "600s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      aggregations {
        alignment_period    = "600s"
        per_series_aligner  = "ALIGN_RATE"
      }
    }
  }

  notification_channels = []
}

resource "google_monitoring_alert_policy" "agent_instance_count" {
  project      = var.project_id
  display_name = "${var.environment} - Instance Count Anomaly"
  combiner     = "OR"

  conditions {
    display_name = "Instance count dropped to zero unexpectedly"

    condition_threshold {
      filter          = 'resource.type="cloud_run_revision" AND resource.labels.service_name="${google_cloud_run_v2_service.agent.name}" AND metric.type="run.googleapis.com/revision/instance_count"'
      duration        = "300s"
      comparison      = "COMPARISON_EQ"
      threshold_value = 0
      aggregations {
        alignment_period    = "300s"
        per_series_aligner  = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = []
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

output "agent_url" {
  description = "URL of the deployed agent Cloud Run service"
  value       = google_cloud_run_v2_service.agent.uri
}

output "agent_service_account" {
  description = "Service account email for the agent"
  value       = google_service_account.agent_sa.email
}

output "artifact_registry" {
  description = "Artifact Registry repository URL"
  value       = google_artifact_registry_repository.agent_repo.name
}

output "firestore_database" {
  description = "Firestore database name"
  value       = google_firestore_database.agent_db.name
}

output "budget_id" {
  description = "GCP Budget ID"
  value       = google_billing_budget.agent_budget.id
}
