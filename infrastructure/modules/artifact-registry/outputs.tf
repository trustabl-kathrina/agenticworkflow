output "repository_name" {
  description = "Artifact Registry repository name"
  value       = google_artifact_registry_repository.agent_repo.name
}
