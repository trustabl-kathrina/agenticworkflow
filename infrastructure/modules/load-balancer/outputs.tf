output "load_balancer_url" {
  description = "External load balancer URL"
  value       = "http://${google_compute_global_address.agent_lb_ip.address}"
}

output "load_balancer_ip" {
  description = "External load balancer IP address"
  value       = google_compute_global_address.agent_lb_ip.address
}
