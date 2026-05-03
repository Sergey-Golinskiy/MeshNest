"""Celery app — broker = Redis, result backend = Redis."""
from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "meshnest",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.import_tasks",
        "app.tasks.conversion_tasks",
        "app.tasks.maintenance_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_max_tasks_per_child=20,           # перезапуск воркера для борьбы с утечками trimesh
    worker_prefetch_multiplier=1,            # обработка по одному заданию (большие STL)
    result_expires=60 * 60 * 24 * 7,         # 7 дней
    broker_connection_retry_on_startup=True,
    task_default_queue="default",
)


celery_app.conf.beat_schedule = {
    "cleanup-orphan-uploads-hourly": {
        "task": "app.tasks.maintenance_tasks.cleanup_orphan_uploads",
        "schedule": 60 * 60,
    },
    "rebuild-search-index-daily": {
        "task": "app.tasks.maintenance_tasks.rebuild_search_index",
        "schedule": 60 * 60 * 24,
    },
}
