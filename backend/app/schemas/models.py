"""Schemas: model card, file, category tree, tag, import-job."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models._types import (
    FileRole,
    FileType,
    ImportJobStatus,
    ModelStatus,
    PreviewStatus,
    TagType,
    ViewerStatus,
)


# ====== Model ======

class ModelCard(BaseModel):
    """Compact card for gallery."""

    id: uuid.UUID
    slug: str
    title: str
    category_path: str | None
    tags: list[str] = Field(default_factory=list)
    preview_url: str | None
    thumbnails: list[str] = Field(default_factory=list)  # carousel: per-file thumb URLs
    has_stl: bool
    has_step: bool
    has_3mf: bool
    has_images: bool
    has_video: bool
    is_flexi: bool
    is_print_in_place: bool
    is_multipart: bool
    is_reviewed: bool
    status: ModelStatus
    file_count: int


class ModelDetail(ModelCard):
    """Detail view (subset of full ORM, без heavy fields)."""

    original_title: str | None
    description: str | None
    category_id: uuid.UUID | None
    category_confidence: float | None
    is_assembly: bool
    preview_status: PreviewStatus
    viewer_status: ViewerStatus
    source_type: str | None
    source_name: str | None
    source_hash: str | None
    stl_count: int
    step_count: int
    three_mf_count: int
    image_count: int
    video_count: int
    document_count: int
    created_at: datetime
    updated_at: datetime
    imported_at: datetime | None


class ModelListResponse(BaseModel):
    items: list[ModelCard]
    total: int
    page: int
    page_size: int


class FileItem(BaseModel):
    id: uuid.UUID
    file_name: str
    extension: str | None
    file_type: FileType
    role: FileRole
    size_bytes: int
    sha256: str | None
    is_primary: bool
    download_url: str           # presigned URL для скачивания исходника
    thumbnail_url: str | None   # presigned URL до derived/thumbs/{file_id}.png (если задача отработала)
    viewer_url: str | None      # presigned URL до derived/glb/{file_id}.glb для mesh/3MF


# ====== Category ======

class CategoryNode(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    path: str
    sort_order: int
    model_count: int = 0
    children: list[CategoryNode] = Field(default_factory=list)


# ====== Tag ======

class TagOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    type: TagType
    model_count: int = 0


# ====== ImportJob ======

class ImportJobOut(BaseModel):
    id: uuid.UUID
    status: ImportJobStatus
    progress_pct: int
    source_type: str | None
    source_name: str | None
    models_created: int
    files_processed: int
    warnings_count: int
    errors_count: int
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime
