"""Shared SQLAlchemy types and enums for all ORM models."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


def created_at_ts() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


def updated_at_ts() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class UserRole(str, enum.Enum):
    admin = "admin"
    contributor = "contributor"
    viewer = "viewer"


class ModelStatus(str, enum.Enum):
    draft = "draft"
    needs_review = "needs_review"
    ready = "ready"
    hidden = "hidden"
    archived = "archived"


class ViewerStatus(str, enum.Enum):
    pending = "pending"
    glb_ready = "glb_ready"
    stl_direct = "stl_direct"
    conversion_failed = "conversion_failed"


class PreviewStatus(str, enum.Enum):
    pending = "pending"
    ready = "ready"
    generated = "generated"
    source_image_used = "source_image_used"
    extracted_from_3mf = "extracted_from_3mf"
    placeholder = "placeholder"
    failed = "failed"


class ImportJobStatus(str, enum.Enum):
    queued = "queued"
    uploading = "uploading"
    extracting = "extracting"
    scanning = "scanning"
    grouping = "grouping"
    classifying = "classifying"
    generating_previews = "generating_previews"
    packaging = "packaging"
    completed = "completed"
    completed_with_warnings = "completed_with_warnings"
    failed = "failed"


class FileRole(str, enum.Enum):
    print_file = "print_file"
    preview_image = "preview_image"
    gallery_image = "gallery_image"
    video = "video"
    instruction = "instruction"
    license = "license"
    source = "source"
    nested_archive = "nested_archive"
    other = "other"


class FileType(str, enum.Enum):
    mesh = "mesh"
    cad = "cad"
    project = "project"
    image = "image"
    video = "video"
    document = "document"
    archive = "archive"
    other = "other"


class TagType(str, enum.Enum):
    topic = "topic"
    print = "print"
    technical = "technical"
    source = "source"
    status = "status"
