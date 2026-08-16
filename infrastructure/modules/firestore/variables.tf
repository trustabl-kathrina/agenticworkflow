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

variable "apis_module" {
  description = "APIs module output for dependency management"
  type        = any
  default     = null
}
