resource "google_billing_budget" "agent_budget" {
  billing_account = var.billing_account_id
  display_name    = "${var.environment}-agentic-workflow-budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
    services = [
      "services/run.googleapis.com",
      "services/aiplatform.googleapis.com",
      "services/artifactregistry.googleapis.com",
      "services/secretmanager.googleapis.com",
      "services/firestore.googleapis.com",
      "services/pubsub.googleapis.com",
      "services/monitoring.googleapis.com",
    ]
  }

  amount {
    specified_amount {
      currency_code = "EUR"
      units         = var.budget_amount
    }
  }

  threshold_rules {
    threshold_percent = 0.5
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.8
    spend_basis       = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "CURRENT_SPEND"
  }

  all_updates_rule {
    disable_default_iam_recipients = false
    monitoring_notification_channels = []
  }
}
