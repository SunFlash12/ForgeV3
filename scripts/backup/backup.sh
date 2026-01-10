#!/bin/bash
#
# Neo4j Backup Shell Script
#
# Usage:
#   ./backup.sh              # Full backup
#   ./backup.sh --incremental  # Incremental backup
#
# Environment variables required (from .env):
#   NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
#
# Schedule with cron:
#   # Daily full backup at 2 AM
#   0 2 * * * /path/to/backup.sh >> /var/log/forge/backup.log 2>&1
#
#   # Hourly incremental backup
#   0 * * * * /path/to/backup.sh --incremental >> /var/log/forge/backup.log 2>&1

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups/neo4j}"

# SECURITY FIX (Audit 4 - L8): Safer .env parsing
# The previous 'export $(grep ... | xargs)' approach could execute shell metacharacters
# This safer approach reads line by line and validates each variable
if [ -f "$PROJECT_ROOT/.env" ]; then
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        # Trim whitespace from key
        key=$(echo "$key" | xargs)
        # Skip if key doesn't look like a valid env var name
        [[ ! "$key" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]] && continue
        # Remove surrounding quotes from value if present
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"
        # Export the variable
        export "$key=$value"
    done < "$PROJECT_ROOT/.env"
fi

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

echo "=========================================="
echo "Forge Neo4j Backup"
echo "Date: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "=========================================="

# Run the Python backup script
cd "$PROJECT_ROOT/forge-cascade-v2"

if [ -f "$PROJECT_ROOT/forge-cascade-v2/.venv/bin/python" ]; then
    PYTHON="$PROJECT_ROOT/forge-cascade-v2/.venv/bin/python"
elif command -v python3 &> /dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

$PYTHON "$SCRIPT_DIR/neo4j_backup.py" \
    --backup-dir "$BACKUP_DIR" \
    --retention-days "${RETENTION_DAYS:-30}" \
    "$@"

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "Backup completed successfully"

    # Optional: Upload to S3 or other storage
    if [ -n "$BACKUP_S3_BUCKET" ]; then
        echo "Uploading to S3..."
        LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/neo4j_backup_*.json.gz | head -1)
        aws s3 cp "$LATEST_BACKUP" "s3://$BACKUP_S3_BUCKET/neo4j/"
        echo "Uploaded to s3://$BACKUP_S3_BUCKET/neo4j/"
    fi

    # Optional: Webhook notification
    if [ -n "$BACKUP_WEBHOOK_URL" ]; then
        curl -X POST "$BACKUP_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"status\":\"success\",\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"}" \
            || true
    fi
else
    echo "Backup failed with exit code $EXIT_CODE"

    # Optional: Error notification webhook
    if [ -n "$BACKUP_WEBHOOK_URL" ]; then
        curl -X POST "$BACKUP_WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"status\":\"failed\",\"exit_code\":$EXIT_CODE,\"timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\"}" \
            || true
    fi
fi

exit $EXIT_CODE
