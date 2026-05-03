"""Schemas: chunked upload + import-package trigger."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UploadInitRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=500)
    total_size: int = Field(ge=1)
    expected_sha256: str | None = Field(default=None, min_length=64, max_length=64)


class UploadInitResponse(BaseModel):
    upload_id: str
    chunk_size: int
    total_chunks: int


class UploadStatus(BaseModel):
    upload_id: str
    filename: str
    total_size: int
    chunk_size: int
    total_chunks: int
    received_chunks: list[int]
    finalized_at: datetime | None
    storage_key: str | None


class ImportPackageRequest(BaseModel):
    upload_id: str


class ImportPackageResponse(BaseModel):
    import_job_id: uuid.UUID
    status: str
