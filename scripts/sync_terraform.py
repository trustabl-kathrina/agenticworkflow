#!/usr/bin/env python3
"""Sync .env values to Terraform variables."""
from __future__ import annotations

import os
from pathlib import Path


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dictionary."""
    env: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    env_file = root / ".env"
    tfvars = root / "infrastructure" / "environments" / "prod" / "terraform.tfvars"

    if not env_file.exists():
        raise FileNotFoundError(f".env not found at {env_file}")

    env = parse_env_file(env_file)

    project_id = env.get("GOOGLE_CLOUD_PROJECT", "")
    region = env.get("GOOGLE_CLOUD_LOCATION", "europe-west3")
    billing_account_id = env.get("BILLING_ACCOUNT_ID", "")
    budget_amount = env.get("BUDGET_AMOUNT", "10")

    if not project_id:
        raise ValueError("GOOGLE_CLOUD_PROJECT is required in .env")
    if not billing_account_id:
        raise ValueError("BILLING_ACCOUNT_ID is required in .env")

    content = f"""project_id      = "{project_id}"
region          = "{region}"
environment     = "prod"
billing_account_id = "{billing_account_id}"

agent_service_name = "agentic-workflow"
agent_image        = "europe-west3-docker.pkg.dev/{project_id}/prod-agentic-workflow/agent:latest"
agent_cpu          = "2"
agent_memory       = "4Gi"
min_instances      = 0
max_instances      = 20
allowed_ingress    = "INGRESS_TRAFFIC_ALL"
budget_amount      = {budget_amount}  # EUR/month hard cap
"""

    tfvars.write_text(content)
    print(f"Synced .env → {tfvars}")


if __name__ == "__main__":
    main()
