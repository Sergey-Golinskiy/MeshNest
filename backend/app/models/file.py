from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._types import FileRole, FileType, created_at_ts, uuid_pk

if TYPE_CHECKING:
    from app.models.model import Model


class File(Base):
    __tablename__ = "files"
    __table_args__ = (
        Index("ix_files_sha256", "sha256"),
        Index("ix_files_model_role", "model_id", "role"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("models.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    original_file_name: Mapped[str | None] = mapped_column(String(500))
    extension: Mapped[str | None] = mapped_column(String(20))

    file_type: Mapped[FileType] = mapped_column(
        Enum(FileType, name="file_type"),
        nullable=False,
        default=FileType.other,
    )
    role: Mapped[FileRole] = mapped_column(
        Enum(FileRole, name="file_role"),
        nullable=False,
        default=FileRole.other,
    )

    storage_key: Mapped[str] = mapped_column(String(700), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))

    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="ready")

    created_at: Mapped[datetime] = created_at_ts()

    model: Mapped[Model] = relationship(back_populates="files")
