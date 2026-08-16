output "budget_id" {
  description = "GCP Budget ID"
  value       = google_billing_budget.agent_budget.id
}
