from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._types import (
    ModelStatus,
    PreviewStatus,
    ViewerStatus,
    created_at_ts,
    updated_at_ts,
    uuid_pk,
)

if TYPE_CHECKING:
    from app.models.category import Category
    from app.models.file import File
    from app.models.import_job import ImportJob
    from app.models.tag import Tag
    from app.models.user import User


class Model(Base):
    __tablename__ = "models"
    __table_args__ = (
        Index("ix_models_category_status", "category_id", "status"),
        Index("ix_models_imported_at_desc", "imported_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    original_title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category_confidence: Mapped[float | None] = mapped_column(Float)

    status: Mapped[ModelStatus] = mapped_column(
        Enum(ModelStatus, name="model_status"),
        nullable=False,
        default=ModelStatus.needs_review,
    )
    is_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Print flags
    is_flexi: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_print_in_place: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_multipart: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_assembly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Format presence flags
    has_stl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_step: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_3mf: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_images: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_video: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Storage keys (S3 / MinIO)
    preview_storage_key: Mapped[str | None] = mapped_column(String(500))
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(500))
    viewer_storage_key: Mapped[str | None] = mapped_column(String(500))
    package_storage_key: Mapped[str | None] = mapped_column(String(500))

    viewer_status: Mapped[ViewerStatus] = mapped_column(
        Enum(ViewerStatus, name="viewer_status"),
        nullable=False,
        default=ViewerStatus.pending,
    )
    preview_status: Mapped[PreviewStatus] = mapped_column(
        Enum(PreviewStatus, name="preview_status"),
        nullable=False,
        default=PreviewStatus.pending,
    )

    # Source provenance
    source_type: Mapped[str | None] = mapped_column(String(50))
    source_name: Mapped[str | None] = mapped_column(String(500))
    source_hash: Mapped[str | None] = mapped_column(String(80))

    # Counts (denormalized для быстрого UI)
    stl_count: Mapped[int] = mapped_column(nullable=False, default=0)
    step_count: Mapped[int] = mapped_column(nullable=False, default=0)
    three_mf_count: Mapped[int] = mapped_column(nullable=False, default=0)
    image_count: Mapped[int] = mapped_column(nullable=False, default=0)
    video_count: Mapped[int] = mapped_column(nullable=False, default=0)
    document_count: Mapped[int] = mapped_column(nullable=False, default=0)

    import_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("import_jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = created_at_ts()
    updated_at: Mapped[datetime] = updated_at_ts()
    imported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    # Relationships
    category: Mapped[Category | None] = relationship(back_populates="models")
    files: Mapped[list[File]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )
    tags: Mapped[list[Tag]] = relationship(secondary="model_tags", back_populates="models")
    import_job: Mapped[ImportJob | None] = relationship(back_populates="models")
    uploader: Mapped[User | None] = relationship(foreign_keys=[uploaded_by])
