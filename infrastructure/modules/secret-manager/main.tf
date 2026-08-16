resource "google_secret_manager_secret" "api_keys" {
  for_each = toset([
    "gemini-api-key",
    "reddit-client-id",
    "reddit-client-secret",
    "developer-knowledge-key",
    "api-key",
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
