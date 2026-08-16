variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west3"
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "alert_email" {
  description = "Email address for monitoring alerts"
  type        = string
  default     = ""
}

variable "cloud_run_service_name" {
  description = "Cloud Run service name for monitoring filters"
  type        = string
}

variable "budget_id" {
  description = "GCP Budget ID for burn rate alerts"
  type        = string
  default     = ""
}
