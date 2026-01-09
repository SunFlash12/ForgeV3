#!/bin/bash
#
# Backup service entrypoint
# Runs scheduled backups using built-in cron or one-shot mode
#

set -e

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Function to run backup
run_backup() {
    local backup_type="${1:-full}"
    echo "=========================================="
    echo "Starting $backup_type backup"
    echo "Time: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
    echo "=========================================="

    ARGS="--backup-dir $BACKUP_DIR --retention-days $RETENTION_DAYS"

    if [ "$backup_type" = "incremental" ]; then
        ARGS="$ARGS --incremental"
    fi

    python /app/neo4j_backup.py $ARGS

    echo "Backup completed at $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
}

# Check for one-shot mode
if [ "$1" = "backup" ]; then
    run_backup "${2:-full}"
    exit $?
fi

if [ "$1" = "restore" ]; then
    shift
    python /app/neo4j_restore.py "$@"
    exit $?
fi

# Scheduled mode - run initial backup then schedule
echo "Forge Backup Service Starting"
echo "  Backup Schedule: ${BACKUP_SCHEDULE:-0 2 * * *}"
echo "  Incremental Schedule: ${INCREMENTAL_SCHEDULE:-0 */6 * * *}"
echo "  Retention Days: $RETENTION_DAYS"
echo "  Backup Directory: $BACKUP_DIR"

# Run initial backup
run_backup "full"

# Install cron schedules
cat > /etc/crontab << EOF
# Full backup (default: 2 AM daily)
${BACKUP_SCHEDULE:-0 2 * * *} root cd /app && python neo4j_backup.py --backup-dir $BACKUP_DIR --retention-days $RETENTION_DAYS >> /var/log/backup.log 2>&1

# Incremental backup (default: every 6 hours)
${INCREMENTAL_SCHEDULE:-0 */6 * * *} root cd /app && python neo4j_backup.py --backup-dir $BACKUP_DIR --retention-days $RETENTION_DAYS --incremental >> /var/log/backup.log 2>&1
EOF

# Start cron daemon
echo "Starting cron daemon..."
cron -f
