"""Celery task: process_import_package."""
from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select

from app.db_sync import SyncSession
from app.models import Model
from app.services.import_package import process_import_package_sync
from app.tasks.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(bind=True, name="app.tasks.import_tasks.process_import_package", max_retries=2)
def process_import_package(self, import_job_id: str, package_storage_key: str) -> dict:
    job_uuid = uuid.UUID(import_job_id)
    log.info("celery.import.start", job=import_job_id, key=package_storage_key)
    with SyncSession() as session:
        try:
            res = process_import_package_sync(session, job_uuid, package_storage_key)
            session.commit()
        except Exception as exc:
            session.rollback()
            log.error("celery.import.error", error=str(exc))
            raise

        # Kick GLB conversion + 3MF thumbnail extraction для всех моделей этого джоба
        from app.tasks.conversion_tasks import extract_3mf_thumbnail, stl_to_glb

        new_models = (
            session.execute(
                select(Model.id, Model.has_stl, Model.has_3mf).where(Model.import_job_id == job_uuid)
            ).all()
        )
        for mid, has_stl, has_3mf in new_models:
            if has_stl:
                stl_to_glb.delay(str(mid))
            if has_3mf:
                extract_3mf_thumbnail.delay(str(mid))

        # Index в Meilisearch (best-effort — не падаем если Meili недоступен)
        try:
            from sqlalchemy.orm import selectinload

            from app.services import search as search_svc

            search_svc.ensure_index()
            full_models = (
                session.execute(
                    select(Model)
                    .options(selectinload(Model.tags), selectinload(Model.category))
                    .where(Model.import_job_id == job_uuid)
                )
                .scalars()
                .all()
            )
            r = search_svc.index_models(full_models)
            log.info("celery.import.indexed", count=r["indexed"])
        except Exception as exc:
            log.warning("celery.import.index_failed", error=str(exc))
    return res
