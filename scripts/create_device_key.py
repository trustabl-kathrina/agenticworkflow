#!/usr/bin/env python3
"""Create a per-device API key valid for N hours."""

import argparse
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_env():
    if not ENV_FILE.exists():
        print(f"Missing .env at {ENV_FILE}")
        sys.exit(1)
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def get_secret_value(project: str, secret_id: str) -> str:
    result = subprocess.run(
        [
            "gcloud",
            "secrets",
            "versions",
            "access",
            "latest",
            f"--secret={secret_id}",
            f"--project={project}",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def add_secret_version(project: str, secret_id: str, payload: str):
    subprocess.run(
        [
            "gcloud",
            "secrets",
            "versions",
            "add",
            secret_id,
            f"--project={project}",
            "--data-file=-",
        ],
        input=payload,
        text=True,
        check=True,
    )


def generate_key() -> str:
    return secrets.token_hex(32)


def main():
    parser = argparse.ArgumentParser(description="Create a per-device API key")
    parser.add_argument("--device-id", required=True, help="Unique device identifier")
    parser.add_argument("--hours", type=int, default=24, help="Validity in hours (default: 24)")
    parser.add_argument("--secret-id", default="api-key", help="Secret Manager secret ID")
    args = parser.parse_args()

    env = load_env()
    project = env.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        print("GOOGLE_CLOUD_PROJECT not set in .env")
        sys.exit(1)

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", args.device_id):
        print("device-id must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}")
        sys.exit(1)

    raw = get_secret_value(project, args.secret_id)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = {"master_key": raw, "devices": []}

    if "master_key" not in data:
        data["master_key"] = generate_key()
    if "devices" not in data:
        data["devices"] = []

    now = datetime.now(timezone.utc)
    expires = now + timedelta(hours=args.hours)

    new_device = {
        "id": args.device_id,
        "key": generate_key(),
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }

    data["devices"].append(new_device)

    add_secret_version(project, args.secret_id, json.dumps(data))

    print(f"Device ID : {new_device['id']}")
    print(f"API Key   : {new_device['key']}")
    print(f"Expires   : {new_device['expires_at']}")


if __name__ == "__main__":
    main()
