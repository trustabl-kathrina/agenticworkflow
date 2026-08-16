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
  default     = "INGRESS_INTERNAL_LOAD_BALANCER"
}

variable "vpc_connector_name" {
  description = "VPC connector name for private egress (leave empty to disable)"
  type        = string
  default     = ""
}

variable "vpc_connector_region" {
  description = "Region for the VPC connector"
  type        = string
  default     = ""
}

variable "vpc_connector_ip_cidr_range" {
  description = "IP CIDR range for VPC connector (e.g., 10.8.0.0/28)"
  type        = string
  default     = "10.8.0.0/28"
}

variable "vpc_egress_all_egress" {
  description = "Send all egress through VPC connector"
  type        = bool
  default     = true
}
