output "agent_sa_email" {
  description = "Agent service account email"
  value       = google_service_account.agent_sa.email
}
