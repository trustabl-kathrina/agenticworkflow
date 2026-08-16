output "agent_url" {
  description = "Cloud Run service URL"
  value       = google_cloud_run_v2_service.agent.uri
}

output "agent_service_name" {
  description = "Cloud Run service name"
  value       = google_cloud_run_v2_service.agent.name
}
