#!/usr/bin/env bash
# LAN-only fast path: bypass Cloudflare + chunked upload, kick import directly.
# Использовать только когда у тебя есть SSH/LAN-доступ на mini-PC.
# Просто кладёт исходный zip в meshnest-imports bucket и создаёт ImportJob.
#
# Usage:  bash deploy/scripts/local-import.sh /path/to/meshnest_import_package.zip
set -euo pipefail

ZIP="${1:?provide path to meshnest_import_package.zip}"
[ -f "$ZIP" ] || { echo "ERROR: $ZIP not found"; exit 1; }

CMP="$(dirname "$0")/../docker-compose.yml"
KEY="uploads/manual-$(date -u +%Y%m%dT%H%M%SZ)/$(basename "$ZIP")"

echo "[1/3] Copy zip into MinIO bucket meshnest-imports as $KEY"
docker compose -f "$CMP" cp "$ZIP" minio:/tmp/import.zip
docker compose -f "$CMP" exec -T minio sh -c "
  mc alias set local http://localhost:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null 2>&1 || true;
  mc mb -p local/meshnest-imports >/dev/null 2>&1 || true;
  mc cp /tmp/import.zip local/meshnest-imports/$KEY;
  rm -f /tmp/import.zip
"

echo "[2/3] Trigger import via Celery directly"
docker compose -f "$CMP" exec -T api python -c "
import uuid
from app.db_sync import SyncSession
from app.models import ImportJob
from app.models._types import ImportJobStatus
from app.tasks.import_tasks import process_import_package

with SyncSession() as s:
    job = ImportJob(
        status=ImportJobStatus.queued,
        source_type='local_import_package',
        source_name='$(basename "$ZIP")',
        package_storage_key='$KEY',
    )
    s.add(job)
    s.commit()
    print(f'job_id={job.id}')
    process_import_package.delay(str(job.id), '$KEY')
"

echo "[3/3] Watch progress: docker compose logs -f worker"
