resource "google_vpc_access_connector" "agent_connector" {
  count   = var.vpc_connector_name != "" ? 1 : 0
  project = var.project_id
  name    = var.vpc_connector_name
  region  = var.vpc_connector_region != "" ? var.vpc_connector_region : var.region
  ip_cidr_range = var.vpc_connector_ip_cidr_range
}

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
        name = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "True"
      }
      env {
        name = "ENVIRONMENT"
        value = var.environment
      }

      env {
        name = "API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_keys["api-key"].secret_id
            version = "latest"
          }
        }
      }

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

    dynamic "vpc_access" {
      for_each = var.vpc_connector_name != "" ? [1] : []
      content {
        connector = google_vpc_access_connector.agent_connector[0].id
        egress    = var.vpc_egress_all_egress ? "ALL_TRAFFIC" : "PRIVATE_RANGES_ONLY"
      }
    }
  }

  depends_on = [google_project_service.api["run.googleapis.com"]]
}
