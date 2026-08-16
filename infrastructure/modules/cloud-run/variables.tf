variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "agent_service_name" {
  description = "Cloud Run service name"
  type        = string
  default     = "agentic-workflow"
}

variable "agent_image" {
  description = "Container image"
  type        = string
}

variable "agent_cpu" {
  description = "CPU allocation"
  type        = string
  default     = "1"
}

variable "agent_memory" {
  description = "Memory allocation"
  type        = string
  default     = "2Gi"
}

variable "min_instances" {
  description = "Minimum instances"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum instances"
  type        = number
  default     = 10
}

variable "allowed_ingress" {
  description = "Allowed ingress"
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}
