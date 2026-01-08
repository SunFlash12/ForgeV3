# Forge V3 - Cascade API Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY forge/ ./forge/
COPY scripts/ ./scripts/
COPY run_compliance.py .
COPY run_virtuals.py .

# Create non-root user
RUN useradd -m -u 1000 forge && chown -R forge:forge /app
USER forge

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Default command - Cascade API
CMD ["python", "-m", "uvicorn", "forge.api.app:app", "--host", "0.0.0.0", "--port", "8001"]
