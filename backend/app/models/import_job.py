from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._types import ImportJobStatus, created_at_ts, updated_at_ts, uuid_pk

if TYPE_CHECKING:
    from app.models.model import Model
    from app.models.user import User


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()

    status: Mapped[ImportJobStatus] = mapped_column(
        Enum(ImportJobStatus, name="import_job_status"),
        nullable=False,
        default=ImportJobStatus.queued,
        index=True,
    )
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    source_type: Mapped[str | None] = mapped_column(String(50))   # archive | folder | local_import_package
    source_name: Mapped[str | None] = mapped_column(String(500))
    package_storage_key: Mapped[str | None] = mapped_column(String(500))
    log_storage_key: Mapped[str | None] = mapped_column(String(500))

    models_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    files_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error_message: Mapped[str | None] = mapped_column(Text)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = created_at_ts()
    updated_at: Mapped[datetime] = updated_at_ts()

    creator: Mapped[User | None] = relationship(foreign_keys=[created_by])
    models: Mapped[list[Model]] = relationship(back_populates="import_job")
