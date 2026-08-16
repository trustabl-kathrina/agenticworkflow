variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "europe-west3"
}

variable "cloud_run_service_name" {
  description = "Cloud Run service name to route traffic to"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}
