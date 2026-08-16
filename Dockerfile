# =============================================================================
# AgenticWorkflow - Production-Ready Dockerfile
# =============================================================================
# Multi-stage build for minimal image size and fast cold starts on Cloud Run.
# =============================================================================

FROM python:3.12-slim AS runtime

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first for layer caching
COPY pyproject.toml .

# Install Python dependencies
RUN pip install --no-cache-dir \
    "google-adk>=0.1.0" \
    "google-genai>=1.0.0" \
    "mcp>=1.0.0" \
    "fastmcp>=2.13.0" \
    "fastapi>=0.110.0" \
    "uvicorn[standard]>=0.29.0" \
    "pydantic>=2.0.0" \
    "pydantic-settings>=2.0.0" \
    "google-cloud-aiplatform>=1.38.0" \
    "google-cloud-logging>=3.0.0" \
    "google-cloud-storage>=3.6.0" \
    "google-cloud-secret-manager>=2.26.0" \
    "google-cloud-firestore>=2.16.0" \
    "python-dotenv>=1.0.0" \
    "tenacity>=8.0.0" \
    "structlog>=23.0.0"

# Copy application source
COPY src/ ./src/
COPY scripts/ ./scripts/

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app

# Environment variables (overridable at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    PORT=8080 \
    GOOGLE_GENAI_USE_VERTEXAI=True

# Switch to non-root user
USER appuser

# Expose port (Cloud Run uses PORT env var)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Entry point
CMD ["python", "-m", "agentic_workflow.api.server"]
