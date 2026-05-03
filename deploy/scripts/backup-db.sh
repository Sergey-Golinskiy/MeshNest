#!/usr/bin/env bash
# Daily Postgres backup → /srv/meshnest/backups/pg-{date}.sql.gz
# Запуск: bash deploy/scripts/backup-db.sh  (crontab @daily)
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/srv/meshnest/backups}"
RETAIN_DAYS="${RETAIN_DAYS:-14}"
DATE="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_DIR}/pg-${DATE}.sql.gz"

mkdir -p "$BACKUP_DIR"

echo "[$(date -u +%FT%TZ)] backup → $OUT"
docker compose -f "$(dirname "$0")/../docker-compose.yml" exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-meshnest}" "${POSTGRES_DB:-meshnest}" \
  | gzip > "$OUT"

# Retention
find "$BACKUP_DIR" -name 'pg-*.sql.gz' -type f -mtime "+${RETAIN_DAYS}" -delete

echo "Done. Size: $(du -h "$OUT" | cut -f1)"

# Optional: rclone to Cloudflare R2 (encrypted via gpg)
if [ -n "${RCLONE_REMOTE:-}" ]; then
  echo "Uploading to remote: $RCLONE_REMOTE"
  rclone copy "$OUT" "${RCLONE_REMOTE}/meshnest-backups/" --progress
fi
