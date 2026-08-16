resource "google_compute_region_network_endpoint_group" "cloud_run_neg" {
  project                  = var.project_id
  name                     = "${var.environment}-agent-neg"
  region                   = var.region
  network_endpoint_type    = "SERVERLESS"
  cloud_run_service        = var.cloud_run_service_name
  cloud_run_tag            = ""
}

resource "google_compute_backend_service" "agent_backend" {
  project       = var.project_id
  name          = "${var.environment}-agent-backend"
  protocol      = "HTTP"
  port_name     = "http"
  timeout_sec   = 30
  security_policy = google_compute_security_policy.cloud_armor.id

  backend {
    group = google_compute_region_network_endpoint_group.cloud_run_neg.id
  }
}

resource "google_compute_url_map" "agent_url_map" {
  project         = var.project_id
  name            = "${var.environment}-agent-url-map"
  default_service = google_compute_backend_service.agent_backend.id
}

resource "google_compute_target_http_proxy" "agent_proxy" {
  project    = var.project_id
  name       = "${var.environment}-agent-proxy"
  url_map    = google_compute_url_map.agent_url_map.id
}

resource "google_compute_global_forwarding_rule" "agent_forwarding" {
  project    = var.project_id
  name       = "${var.environment}-agent-forwarding"
  target     = google_compute_target_http_proxy.agent_proxy.id
  port_range = "80"
  ip_address = google_compute_global_address.agent_lb_ip.address
}

resource "google_compute_global_address" "agent_lb_ip" {
  project    = var.project_id
  name       = "${var.environment}-agent-lb-ip"
  address_type = "EXTERNAL"
}

resource "google_compute_security_policy" "cloud_armor" {
  project = var.project_id
  name    = "${var.environment}-agent-cloud-armor"

  # Rate limiting: 100 requests per minute per IP
  rule {
    action   = "rate_based_ban"
    priority = "100"
    rate_limit_options {
      conform_action  = "allow"
      exceed_action   = "deny(403)"
      enforce_on_key  = "IP"
      rate_limit_threshold {
        count        = 100
        interval_sec = 60
      }
      ban_duration_sec = 600
    }
    match {
      versioned_expr = "CEL_V1"
      expression     = "true"
    }
  }

  # Default rule: allow
  rule {
    action   = "allow"
    priority = "65535"
    match {
      versioned_expr = "CEL_V1"
      expression     = "true"
    }
  }
}
