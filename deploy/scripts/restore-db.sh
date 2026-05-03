#!/usr/bin/env bash
# Restore Postgres from a gzipped pg_dump file.
# Usage: bash deploy/scripts/restore-db.sh /path/to/pg-YYYYMMDD.sql.gz
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <pg-dump.sql.gz>"
  exit 1
fi
DUMP="$1"

if [ ! -f "$DUMP" ]; then
  echo "ERROR: $DUMP not found"
  exit 1
fi

echo "WARNING: this will DROP and recreate the public schema in the meshnest DB."
read -r -p "Type YES to continue: " CONFIRM
[ "$CONFIRM" = "YES" ] || { echo "aborted"; exit 1; }

CMP="$(dirname "$0")/../docker-compose.yml"

docker compose -f "$CMP" exec -T postgres \
  psql -U "${POSTGRES_USER:-meshnest}" -d "${POSTGRES_DB:-meshnest}" \
  -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'

gunzip -c "$DUMP" | docker compose -f "$CMP" exec -T postgres \
  psql -U "${POSTGRES_USER:-meshnest}" -d "${POSTGRES_DB:-meshnest}"

echo "Restore complete."
