resource "google_monitoring_notification_channel" "email" {
  count      = var.alert_email != "" ? 1 : 0
  project    = var.project_id
  display_name = "${var.environment} - Alert Email"
  type       = "email"
  labels = {
    email_address = var.alert_email
  }
}

resource "google_monitoring_alert_policy" "agent_errors" {
  project      = var.project_id
  display_name = "${var.environment} - Agent Error Rate"
  combiner     = "OR"

  conditions {
    display_name = "Agent 5xx errors"

    condition_threshold {
      filter          = 'resource.type="cloud_run_revision" AND resource.labels.service_name="${google_cloud_run_v2_service.agent.name}" AND metric.type="run.googleapis.com/request_count" AND metric.label.response_code_class="5xx"'
      duration        = "60s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      aggregations {
        alignment_period    = "60s"
        per_series_aligner  = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []
}

resource "google_monitoring_alert_policy" "agent_latency" {
  project      = var.project_id
  display_name = "${var.environment} - Agent High Latency"
  combiner     = "OR"

  conditions {
    display_name = "Agent p99 latency > 5s"

    condition_threshold {
      filter          = 'resource.type="cloud_run_revision" AND resource.labels.service_name="${google_cloud_run_v2_service.agent.name}" AND metric.type="run.googleapis.com/request_latencies"'
      duration        = "300s"
      comparison      = "COMPARISON_GT"
      threshold_value = 5000
      aggregations {
        alignment_period    = "300s"
        per_series_aligner  = "ALIGN_PERCENTILE_99"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []
}

resource "google_monitoring_alert_policy" "budget_burn_rate" {
  project      = var.project_id
  display_name = "${var.environment} - Budget Burn Rate Alert"
  combiner     = "OR"

  conditions {
    display_name = "Daily spend exceeds 3 EUR (30% of 10 EUR budget)"

    condition_threshold {
      filter          = 'resource.type="billing_account" AND metric.type="billing.googleapis.com/budget/burn_rate" AND metric.label.budget_id="${google_billing_budget.agent_budget.budget_id}"'
      duration        = "3600s"
      comparison      = "COMPARISON_GT"
      threshold_value = 3.0
      aggregations {
        alignment_period    = "3600s"
        per_series_aligner  = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []
}

resource "google_monitoring_alert_policy" "agent_cold_starts" {
  project      = var.project_id
  display_name = "${var.environment} - High Cold Start Rate"
  combiner     = "OR"

  conditions {
    display_name = "Cold starts > 20% of requests"

    condition_threshold {
      filter          = 'resource.type="cloud_run_revision" AND resource.labels.service_name="${google_cloud_run_v2_service.agent.name}" AND metric.type="run.googleapis.com/container/cold_start_count"'
      duration        = "600s"
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      aggregations {
        alignment_period    = "600s"
        per_series_aligner  = "ALIGN_RATE"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []
}

resource "google_monitoring_alert_policy" "agent_instance_count" {
  project      = var.project_id
  display_name = "${var.environment} - Instance Count Anomaly"
  combiner     = "OR"

  conditions {
    display_name = "Instance count dropped to zero unexpectedly"

    condition_threshold {
      filter          = 'resource.type="cloud_run_revision" AND resource.labels.service_name="${google_cloud_run_v2_service.agent.name}" AND metric.type="run.googleapis.com/revision/instance_count"'
      duration        = "300s"
      comparison      = "COMPARISON_EQ"
      threshold_value = 0
      aggregations {
        alignment_period    = "300s"
        per_series_aligner  = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []
}
