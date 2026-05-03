"""Periodic maintenance: cleanup orphan uploads, rebuild search index."""
from __future__ import annotations

import shutil
import time
from pathlib import Path

import structlog

from app.tasks.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(name="app.tasks.maintenance_tasks.cleanup_orphan_uploads")
def cleanup_orphan_uploads() -> dict:
    """Удаляет директории upload-buffer, которые старше 24 часов и не finalized."""
    root = Path("/var/lib/meshnest/uploads")
    if not root.exists():
        return {"status": "no_dir"}
    now = time.time()
    removed = 0
    for d in root.iterdir():
        try:
            mtime = d.stat().st_mtime
            if now - mtime > 24 * 3600:
                shutil.rmtree(d, ignore_errors=True)
                removed += 1
        except Exception:
            continue
    log.info("cleanup.uploads", removed=removed)
    return {"removed": removed}


@celery_app.task(name="app.tasks.maintenance_tasks.rebuild_search_index")
def rebuild_search_index() -> dict:
    """Полный пересбор Meilisearch индекса `models`."""
    from app.db_sync import SyncSession
    from app.services import search as search_svc

    with SyncSession() as session:
        try:
            res = search_svc.reindex_all(session)
            log.info("search.rebuild.ok", **res)
            return res
        except Exception as exc:
            log.error("search.rebuild.fail", error=str(exc))
            return {"status": "failed", "error": str(exc)}
