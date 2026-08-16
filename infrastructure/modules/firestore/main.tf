resource "google_firestore_database" "agent_db" {
  project      = var.project_id
  name         = "(default)"
  location_id  = var.region
  type         = "FIRESTORE_NATIVE"

  depends_on = [var.apis_module]
}
