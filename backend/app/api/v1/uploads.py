"""Chunked upload endpoints — обходят CF Free 100 MB лимит на request body."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from app.config import settings
from app.core.ratelimit import limiter
from app.deps import require_contributor
from app.models import User
from app.schemas.uploads import (
    UploadInitRequest,
    UploadInitResponse,
    UploadStatus,
)
from app.services import upload_buffer as ub

router = APIRouter()


@router.post("/uploads/init", response_model=UploadInitResponse)
@limiter.limit(settings.rate_limit_uploads)
async def upload_init(
    request: Request,
    body: UploadInitRequest,
    _user: Annotated[User, Depends(require_contributor)],
) -> UploadInitResponse:
    try:
        meta = ub.init_upload(body.filename, body.total_size, body.expected_sha256)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return UploadInitResponse(
        upload_id=meta.upload_id,
        chunk_size=meta.chunk_size,
        total_chunks=meta.total_chunks,
    )


@router.put("/uploads/{upload_id}/chunk", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(settings.rate_limit_uploads)
async def upload_chunk(
    request: Request,
    upload_id: str,
    n: Annotated[int, Query(ge=0)],
    _user: Annotated[User, Depends(require_contributor)],
) -> None:
    """Принимает binary body чанка. Размер enforced на serv-конфиге nginx (`client_max_body_size 100m`)."""
    raw = await request.body()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Empty body")
    if len(raw) > settings.upload_chunk_max_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Chunk too large")
    try:
        ub.write_chunk(upload_id, n, raw)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.get("/uploads/{upload_id}", response_model=UploadStatus)
async def upload_status(
    upload_id: str,
    _user: Annotated[User, Depends(require_contributor)],
) -> UploadStatus:
    meta = ub.load_meta(upload_id)
    if meta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    return UploadStatus(
        upload_id=meta.upload_id,
        filename=meta.filename,
        total_size=meta.total_size,
        chunk_size=meta.chunk_size,
        total_chunks=meta.total_chunks,
        received_chunks=meta.received_chunks,
        finalized_at=meta.finalized_at,  # type: ignore[arg-type]
        storage_key=meta.storage_key,
    )


@router.post("/uploads/{upload_id}/complete", response_model=UploadStatus)
@limiter.limit(settings.rate_limit_uploads)
async def upload_complete(
    request: Request,
    upload_id: str,
    _user: Annotated[User, Depends(require_contributor)],
) -> UploadStatus:
    try:
        meta = await ub.complete_upload(upload_id)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return UploadStatus(
        upload_id=meta.upload_id,
        filename=meta.filename,
        total_size=meta.total_size,
        chunk_size=meta.chunk_size,
        total_chunks=meta.total_chunks,
        received_chunks=meta.received_chunks,
        finalized_at=meta.finalized_at,  # type: ignore[arg-type]
        storage_key=meta.storage_key,
    )
