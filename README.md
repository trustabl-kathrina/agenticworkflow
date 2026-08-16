# AgenticWorkflow

Extensible AI agent platform on Google Cloud. Framework-agnostic core with pluggable tools, memory, and hard budget caps.

## Getting Started

### Prerequisites

- Python 3.12+, `uv`
- Terraform >= 1.6.0
- Docker
- gcloud CLI authenticated (`gcloud auth login`)
- Active GCP project with billing enabled


### Production Deployment

#### 1. Configure Environment

Edit `.env` with your GCP project and billing details:

```bash
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=europe-west3
BILLING_ACCOUNT_ID=your-billing-account-id
BUDGET_AMOUNT=10
API_KEY=your-secret-api-key
```

The `scripts/sync_terraform.py` script syncs these values to `terraform.tfvars` automatically.

#### 2. Enable Required APIs

Some APIs must be enabled before Terraform can manage them:

```bash
gcloud services enable cloudresourcemanager.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  --project=your-project-id
```

**Why?** Terraform's `google_project_service` resource is eventually consistent. The provider may attempt to read/write other services before GCP has finished propagating the enablement, causing `SERVICE_DISABLED` errors.

#### 3. Set Quota Project

The Budgets API requires a quota project when using local ADC:

```bash
export GOOGLE_CLOUD_QUOTA_PROJECT=your-project-id
```

Or set it in your shell profile. Terraform providers are configured with `user_project_override = true` to use this automatically.

#### 4. Initialize Terraform

```bash
make tf-init
```

This runs `scripts/sync_terraform.py` then `terraform init` with the GCS backend.

**Note:** The GCS backend bucket must exist first:

```bash
gsutil mb gs://your-project-id-terraform-state || true
gsutil versioning set on gs://your-project-id-terraform-state
```

#### 5. Plan Infrastructure

```bash
make tf-plan
```

#### 6. Apply Infrastructure

```bash
make tf-apply
```

This creates: APIs, Artifact Registry, IAM, Secret Manager, Firestore, Cloud Run, Load Balancer, Budget, and Monitoring.

**Important:** Cloud Run will fail health checks until a valid Docker image is deployed.

#### 7. Build and Push Docker Image

```bash
make deploy
```

Or manually:

```bash
gcloud builds submit \
  --project your-project-id \
  --region europe-west3 \
  --tag europe-west3-docker.pkg.dev/your-project-id/prod-agentic-workflow/agent:latest
```

#### 8. Provision API Key Secret

Terraform creates the `api-key` secret, but you must add the value:

```bash
echo -n "your-secret-api-key" | gcloud secrets versions add api-key \
  --project=your-project-id \
  --data-file=-
```

#### 9. Verify Deployment

```bash
# Get load balancer URL
terraform output load_balancer_url

# Test health endpoint
curl http://<LOAD_BALANCER_IP>/health

# Test authenticated endpoint
curl -H "X-API-Key: your-secret-api-key" http://<LOAD_BALANCER_IP>/health
```

### Calling the Service

All endpoints are served through the load balancer at `http://<LOAD_BALANCER_IP>`. Authenticated endpoints require the `X-API-Key` header.

#### Prerequisites

```bash
# Set the correct GCP project
gcloud config set project your-project-id

# Get the load balancer IP
export LB_IP=$(terraform output -raw load_balancer_url | sed 's|http://||')

# Get the API key from Secret Manager
export API_KEY=$(gcloud secrets versions access latest --secret=api-key --project=your-project-id)
```

#### Health Check

```bash
curl http://$LB_IP/health
```

Response:
```json
{"status":"healthy"}
```

#### Chat

Send a message and receive a response:

```bash
curl -X POST http://$LB_IP/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "Hello, how are you?"}'
```

Response:
```json
{
  "message": "Hello! How can I help you today?",
  "session_id": "default",
  "tool_calls": [],
  "finish_reason": "stop",
  "usage": {"prompt_tokens": 23, "completion_tokens": 9}
}
```

#### Streaming Chat

Stream responses in real time:

```bash
curl -X POST http://$LB_IP/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "Tell me a story"}'
```

#### List Tools

```bash
curl http://$LB_IP/tools \
  -H "X-API-Key: $API_KEY"
```

Response:
```json
["tool_name_1", "tool_name_2"]
```

#### Register Tool

```bash
curl -X POST http://$LB_IP/tools/register \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "name": "my_tool",
    "description": "My custom tool",
    "parameters": {"type": "object", "properties": {...}},
    "function": "base64_encoded_python_function"
  }'
```

#### Invoke Tool

```bash
curl -X POST http://$LB_IP/tools/my_tool/invoke \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"arg1": "value1", "arg2": "value2"}'
```

#### Delete Session

```bash
curl -X DELETE http://$LB_IP/sessions/default \
  -H "X-API-Key: $API_KEY"
```



