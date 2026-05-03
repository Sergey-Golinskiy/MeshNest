"""POST /api/v1/import-package — kick off Celery import job."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_contributor
from app.models import ImportJob, User
from app.models._types import ImportJobStatus
from app.schemas.uploads import ImportPackageRequest, ImportPackageResponse
from app.services import upload_buffer as ub

router = APIRouter()


@router.post("/import-package", response_model=ImportPackageResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_import(
    body: ImportPackageRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(require_contributor)],
) -> ImportPackageResponse:
    meta = ub.load_meta(body.upload_id)
    if meta is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    if not meta.finalized_at or not meta.storage_key:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Upload not finalized — call /uploads/{id}/complete first",
        )

    job = ImportJob(
        status=ImportJobStatus.queued,
        source_type="local_import_package",
        source_name=meta.filename,
        package_storage_key=meta.storage_key,
        created_by=user.id,
    )
    session.add(job)
    await session.flush()

    # Kick Celery
    from app.tasks.import_tasks import process_import_package

    process_import_package.delay(str(job.id), meta.storage_key)

    return ImportPackageResponse(import_job_id=job.id, status=job.status.value)
