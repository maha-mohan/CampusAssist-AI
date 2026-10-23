#!/bin/sh
# Daily database backup. Add to the server crontab, e.g.:
#   30 2 * * * /opt/college-ai-helpdesk/infra/scripts/backup.sh
set -e
cd "$(dirname "$0")/../.."
mkdir -p backups
STAMP=$(date +%Y%m%d_%H%M)
docker compose exec -T postgres pg_dump -U helpdesk helpdesk | gzip > "backups/helpdesk_$STAMP.sql.gz"
# keep 14 days
find backups -name 'helpdesk_*.sql.gz' -mtime +14 -delete
echo "Backup written: backups/helpdesk_$STAMP.sql.gz"
