"""GET /api/v1/import-jobs, GET /api/v1/import-jobs/{id}."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_contributor
from app.models import ImportJob, User
from app.schemas.models import ImportJobOut

router = APIRouter()


@router.get("/import-jobs", response_model=list[ImportJobOut])
async def list_import_jobs(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_contributor)],
    limit: int = 50,
) -> list[ImportJobOut]:
    rows = (
        await session.execute(
            select(ImportJob).order_by(desc(ImportJob.created_at)).limit(limit)
        )
    ).scalars().all()
    return [ImportJobOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("/import-jobs/{job_id}", response_model=ImportJobOut)
async def get_import_job(
    job_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[User, Depends(require_contributor)],
) -> ImportJobOut:
    job = await session.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Import job not found")
    return ImportJobOut.model_validate(job, from_attributes=True)
