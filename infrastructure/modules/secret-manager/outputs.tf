output "secret_ids" {
  description = "Secret IDs"
  value       = { for k, v in google_secret_manager_secret.api_keys : k => v.secret_id }
}
