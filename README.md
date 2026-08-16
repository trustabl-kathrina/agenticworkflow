# AgenticWorkflow

Extensible AI agent platform on Google Cloud. Framework-agnostic core with pluggable tools, memory, and hard budget caps.

## Getting Started

### Prerequisites

- Python 3.12+, `uv`
- Terraform >= 1.6.0
- Docker
- gcloud CLI authenticated (`gcloud auth login`)
- Active GCP project with billing enabled

### Local Development

```bash
# Install dependencies
make install

# Run server locally
make local

# Run tests
make test

# Lint and typecheck
make check
```

### Production Deployment

#### 1. Configure Environment

Edit `.env` with your GCP project and billing details:

```bash
GOOGLE_CLOUD_PROJECT=agenticworkflow-505710
GOOGLE_CLOUD_LOCATION=europe-west3
BILLING_ACCOUNT_ID=01341C-1027CC-FC941B
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
  --project=agenticworkflow-505710
```

**Why?** Terraform's `google_project_service` resource is eventually consistent. The provider may attempt to read/write other services before GCP has finished propagating the enablement, causing `SERVICE_DISABLED` errors.

#### 3. Set Quota Project

The Budgets API requires a quota project when using local ADC:

```bash
export GOOGLE_CLOUD_QUOTA_PROJECT=agenticworkflow-505710
```

Or set it in your shell profile. Terraform providers are configured with `user_project_override = true` to use this automatically.

#### 4. Initialize Terraform

```bash
make tf-init
```

This runs `scripts/sync_terraform.py` then `terraform init` with the GCS backend.

**Note:** The GCS backend bucket must exist first:

```bash
gsutil mb gs://agenticworkflow-505710-terraform-state || true
gsutil versioning set on gs://agenticworkflow-505710-terraform-state
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
  --project agenticworkflow-505710 \
  --region europe-west3 \
  --tag europe-west3-docker.pkg.dev/agenticworkflow-505710/prod-agentic-workflow/agent:latest
```

#### 8. Provision API Key Secret

Terraform creates the `api-key` secret, but you must add the value:

```bash
echo -n "your-secret-api-key" | gcloud secrets versions add api-key \
  --project=agenticworkflow-505710 \
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

### Known Issues and Resolutions

| Issue | Resolution |
|-------|-----------|
| `Secret Manager API has not been used` | Enable `secretmanager.googleapis.com` manually before `terraform apply` |
| `Compute Engine API has not been used` | Enable `compute.googleapis.com` manually before `terraform apply` |
| `Cloud Resource Manager API has not been used` | Enable `cloudresourcemanager.googleapis.com` manually before `terraform apply` |
| `billingbudgets.googleapis.com requires quota project` | Set `GOOGLE_CLOUD_QUOTA_PROJECT` env var |
| `Image not found` on Cloud Run | Build and push Docker image before `terraform apply`, or deploy image after |
| `COPY` Docker build failure | Ensure `COPY` with multiple sources ends with `/` |

### Latest Updates

- **Firestore Memory**: Fixed `MessageRole` serialization/deserialization to prevent `AttributeError` on session save/load
- **ADK Integration**: Fixed session creation (`await` + `create_session`), switched to `get_function_calls()` API for tool call parsing
- **Server**: Migrated app state from globals to `app.state`, added `__main__` block for direct uvicorn execution
- **Docker**: Fixed `COPY` multi-source syntax, added healthcheck
- **Infrastructure**: Added `depends_on` for API enablement, `user_project_override` for Budgets API, Cloud Armor rate limiting

### Architecture

- **Agent Framework**: ADK (pluggable via `IAgent` interface)
- **Tools**: MCP-based, pluggable via `/tools/register`
- **Memory**: Firestore-backed
- **Auth**: API key via Secret Manager + Cloud Armor rate limiting
- **Budget**: 10 EUR/month hard cap with GCP Budgets
- **Monitoring**: 5 alert policies (errors, latency, burn rate, cold starts, instance count)
- **Region**: `europe-west3`

### CI/CD

GitHub Actions runs on push to `main`:
1. Lint and typecheck
2. Unit tests
3. Build Docker image
4. Integration tests

