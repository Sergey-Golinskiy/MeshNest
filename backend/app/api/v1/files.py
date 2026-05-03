"""GET /api/v1/files/{file_id}/download — presigned redirect to a single file."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import CurrentUser
from app.models import File
from app.services.storage import get_storage

router = APIRouter()


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
) -> RedirectResponse:
    f = await session.get(File, file_id)
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")
    url = await get_storage().presign_get(
        settings.s3_bucket_files, f.storage_key, settings.s3_presigned_ttl
    )
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)
