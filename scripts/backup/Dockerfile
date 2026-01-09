# Dockerfile for Neo4j Backup Service
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies including cron
RUN apt-get update && apt-get install -y --no-install-recommends \
    cron \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    neo4j>=5.0.0 \
    structlog>=24.0.0 \
    tenacity>=8.0.0

# Copy backup scripts
COPY neo4j_backup.py /app/
COPY neo4j_restore.py /app/
COPY entrypoint.sh /app/

RUN chmod +x /app/entrypoint.sh

# Create backup directory
RUN mkdir -p /backups

# Default environment
ENV BACKUP_DIR=/backups
ENV RETENTION_DAYS=30
ENV BACKUP_SCHEDULE="0 2 * * *"
ENV INCREMENTAL_SCHEDULE="0 */6 * * *"

VOLUME ["/backups"]

ENTRYPOINT ["/app/entrypoint.sh"]
