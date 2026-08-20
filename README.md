# AgenticWorkflow

Extensible AI agent platform on Google Cloud. Framework-agnostic core with pluggable tools, memory, and hard budget caps.

### Prerequisites

- Python 3.12+, `uv`
- Terraform >= 1.6.0
- Docker
- gcloud CLI authenticated (`gcloud auth login`)
- Active GCP project with billing enabled


### Production Deployment

#### Configure Environment and Project Settings

Edit `.env` with your GCP project and billing details:

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=europe-west3
BILLING_ACCOUNT_ID=your-billing-account-id
BUDGET_AMOUNT=10
API_KEY=your-secret-api-key
```

The `scripts/sync_terraform.py` script syncs these values to `terraform.tfvars` automatically.

Afterwards, enable required APIs.

```bash
gcloud services enable cloudresourcemanager.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  --project=your-project-id
```

The Budgets API requires a quota project when using local ADC:

```bash
export GOOGLE_CLOUD_QUOTA_PROJECT=your-project-id
```

#### Deploy Infrastructure 

```bash
# The GCS backend bucket must exist first
gsutil mb gs://your-project-id-terraform-state || true
gsutil versioning set on gs://your-project-id-terraform-state

# Run Terraform commands to deploy
make tf-init
make tf-plan
make tf-apply

# Build and Publish Docker Image
make deploy
```

The last step is to provision API key secret. Terraform creates the `api-key` secret, but you must add the value:

```bash
echo -n "your-secret-api-key" | gcloud secrets versions add api-key \
  --project=your-project-id \
  --data-file=-
```

### Calling the Service

Set permissions to access the API.
```bash
# Set the correct GCP project
gcloud config set project your-project-id

# Get the load balancer IP
export LB_IP=$(terraform output -raw load_balancer_url | sed 's|http://||')

# Get the API key from Secret Manager
export API_KEY=$(gcloud secrets versions access latest --secret=api-key --project=your-project-id)
```

The `api-key` secret stores a JSON object with a `master_key` and `devices` array. Use the master key for admin / infrastructure access, or issue per-device keys for MCUs.

Using the following cheat sheet, you can start communicating with your agent.
```
# Health Check
curl http://$LB_IP/health
# {"status":"healthy"}

# Send a message and receive a response.
curl -X POST http://$LB_IP/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "Hello, how are you?"}'
# { "message": "Hello! How can I help you today?", "session_id": "default", "tool_calls": [], "finish_reason": "stop", "usage": {"prompt_tokens": 23, "completion_tokens": 9} }

# Stream responses in real time
curl -X POST http://$LB_IP/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "Tell me a story"}'

# Streaming chat
curl http://$LB_IP/tools \
  -H "X-API-Key: $API_KEY"

# List available tools
curl http://$LB_IP/tools \
  -H "X-API-Key: $API_KEY"
# ["tool_name_1", "tool_name_2"]

# Register a tool
curl -X POST http://$LB_IP/tools/register \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "name": "my_tool",
    "description": "My custom tool",
    "parameters": {"type": "object", "properties": {...}},
    "function": "base64_encoded_python_function"
  }'

# Invoke a tool
curl -X POST http://$LB_IP/tools/my_tool/invoke \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"arg1": "value1", "arg2": "value2"}'

# Delete session
curl -X DELETE http://$LB_IP/sessions/default \
  -H "X-API-Key: $API_KEY"
```

### Per-Device API Keys

Issue short-lived, per-device credentials for MCUs or edge clients. Device keys are stored in the same `api-key` Secret Manager secret as the master key.

#### Create a new device key

```bash
python3 scripts/create_device_key.py --device-id mcu-001 --hours 24
```

The command prints a device-specific key and expiry time. The script preserves the existing master key and appends the new device to the secret's JSON payload.

#### Secret format

```json
{
  "master_key": "...",
  "devices": [
    {
      "id": "mcu-001",
      "key": "...",
      "created_at": "...",
      "expires_at": "..."
    }
  ]
}
```

#### Use a device key

```bash
curl -X POST http://$LB_IP/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <device-key>" \
  -d '{"message": "Hello from MCU"}'
```

Successful requests return `X-Auth-Device-ID: mcu-001` in the response headers. Expired device keys return `401 Authentication failed`.
