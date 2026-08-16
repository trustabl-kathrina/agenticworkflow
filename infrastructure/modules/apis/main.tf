locals {
  required_apis = [
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "cloudbuild.googleapis.com",
    "firestore.googleapis.com",
    "pubsub.googleapis.com",
    "compute.googleapis.com",
  ]
}

resource "google_project_service" "api" {
  for_each = toset(local.required_apis)
  project  = var.project_id
  service  = each.key

  disable_on_destroy = false
}
