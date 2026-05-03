"""Sync SQLAlchemy session — для Celery worker'ов (где async лишний)."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

sync_engine = create_engine(
    settings.database_url_sync,
    pool_size=5,
    max_overflow=2,
    pool_pre_ping=True,
)
SyncSession = sessionmaker(sync_engine, autoflush=False, expire_on_commit=False)


def get_sync_session() -> Iterator[Session]:
    s = SyncSession()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
