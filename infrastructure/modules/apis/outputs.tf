output "apis" {
  description = "Enabled APIs"
  value       = { for k, v in google_project_service.api : k => v.service }
}
