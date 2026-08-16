resource "google_firestore_database" "agent_db" {
  project      = var.project_id
  name         = "(default)"
  location_id  = var.region
  type         = "NATIVE"
  delete_protection_enabled = var.environment == "prod"

  depends_on = [google_project_service.api["firestore.googleapis.com"]]
}
