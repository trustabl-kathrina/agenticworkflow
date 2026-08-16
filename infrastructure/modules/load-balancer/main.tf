locals {
  neg_self_link = "projects/${var.project_id}/regions/${var.region}/networkEndpointGroups/${var.environment}-agent-neg"
}

resource "google_compute_region_network_endpoint_group" "cloud_run_neg" {
  project               = var.project_id
  name                  = "${var.environment}-agent-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = var.cloud_run_service_name
  }
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

resource "google_compute_managed_ssl_certificate" "agent_ssl" {
  count   = var.domain != "" ? 1 : 0
  project = var.project_id
  name    = "${var.environment}-agent-ssl-cert"

  managed {
    domains = [var.domain]
  }
}

resource "google_compute_target_https_proxy" "agent_https_proxy" {
  count           = var.domain != "" ? 1 : 0
  project         = var.project_id
  name            = "${var.environment}-agent-https-proxy"
  url_map         = google_compute_url_map.agent_url_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.agent_ssl[0].id]
}

resource "google_compute_global_forwarding_rule" "agent_https_forwarding" {
  count        = var.domain != "" ? 1 : 0
  project      = var.project_id
  name         = "${var.environment}-agent-https-forwarding"
  target       = google_compute_target_https_proxy.agent_https_proxy[0].id
  port_range   = "443"
  ip_address  = google_compute_global_address.agent_lb_ip.address
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
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }

  rule {
    action   = "allow"
    priority = "2147483647"
    match {
      versioned_expr = "SRC_IPS_V1"
      config {
        src_ip_ranges = ["*"]
      }
    }
  }
}
