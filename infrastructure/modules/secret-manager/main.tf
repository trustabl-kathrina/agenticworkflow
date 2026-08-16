resource "google_secret_manager_secret" "api_keys" {
  for_each = toset([
    "api-key",
  ])

  project   = var.project_id
  secret_id = each.key

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}
