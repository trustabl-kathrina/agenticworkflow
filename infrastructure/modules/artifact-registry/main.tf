resource "google_artifact_registry_repository" "agent_repo" {
  location      = var.region
  project       = var.project_id
  repository_id = "${var.environment}-agentic-workflow"
  description   = "Container images for ${var.environment} agentic workflow"
  format        = "DOCKER"
}
