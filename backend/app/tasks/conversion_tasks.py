"""Celery tasks: STL → GLB conversion, 3MF thumbnail extraction, preview placeholders."""
from __future__ import annotations

import io
import tempfile
import uuid
import zipfile
from pathlib import Path

import boto3
import structlog
import trimesh
from botocore.config import Config as BotoConfig
from sqlalchemy import select

from app.config import settings
from app.db_sync import SyncSession
from app.models import File, Model
from app.models._types import FileType, PreviewStatus, ViewerStatus
from app.tasks.celery_app import celery_app

log = structlog.get_logger()


def _s3():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        region_name=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


@celery_app.task(name="app.tasks.conversion_tasks.stl_to_glb", max_retries=1)
def stl_to_glb(model_id: str) -> dict:
    """Найти первый STL у модели → trimesh → GLB → upload в derived/glb/{model_id}.glb."""
    mid = uuid.UUID(model_id)
    s3 = _s3()
    with SyncSession() as session:
        model = session.get(Model, mid)
        if model is None:
            return {"status": "not_found"}
        if model.viewer_status == ViewerStatus.glb_ready and model.viewer_storage_key:
            return {"status": "already_done"}

        stl_files = (
            session.execute(
                select(File)
                .where(File.model_id == mid, File.file_type == FileType.mesh)
                .order_by(File.is_primary.desc(), File.size_bytes.desc())
            )
            .scalars()
            .all()
        )
        stl_file = next((f for f in stl_files if (f.extension or "").lower() == ".stl"), None)
        if stl_file is None:
            model.viewer_status = ViewerStatus.stl_direct
            session.commit()
            return {"status": "no_stl"}

        try:
            with tempfile.TemporaryDirectory() as tmp:
                local_stl = Path(tmp) / "model.stl"
                s3.download_file(settings.s3_bucket_files, stl_file.storage_key, str(local_stl))
                mesh = trimesh.load(local_stl, force="mesh")
                if not isinstance(mesh, (trimesh.Trimesh, trimesh.Scene)):
                    raise RuntimeError(f"Unexpected trimesh type: {type(mesh)}")
                glb_local = Path(tmp) / "model.glb"
                if isinstance(mesh, trimesh.Trimesh):
                    scene = trimesh.Scene([mesh])
                else:
                    scene = mesh
                scene.export(file_obj=str(glb_local), file_type="glb")

                key = f"glb/{model.id}.glb"
                s3.upload_file(
                    str(glb_local),
                    settings.s3_bucket_derived,
                    key,
                    ExtraArgs={"ContentType": "model/gltf-binary"},
                )
                model.viewer_storage_key = key
                model.viewer_status = ViewerStatus.glb_ready
                session.commit()
                log.info("glb.ok", model_id=model_id, key=key)
                return {"status": "ok", "key": key}
        except Exception as exc:
            session.rollback()
            model = session.get(Model, mid)
            if model:
                model.viewer_status = ViewerStatus.conversion_failed
                session.commit()
            log.error("glb.fail", model_id=model_id, error=str(exc))
            return {"status": "failed", "error": str(exc)}


@celery_app.task(name="app.tasks.conversion_tasks.extract_3mf_thumbnail")
def extract_3mf_thumbnail(model_id: str) -> dict:
    """Если у модели preview_status=pending и есть .3mf — вытащить Metadata/thumbnail.png."""
    mid = uuid.UUID(model_id)
    s3 = _s3()
    with SyncSession() as session:
        model = session.get(Model, mid)
        if model is None or model.preview_status != PreviewStatus.pending:
            return {"status": "skip"}

        threemf_files = (
            session.execute(
                select(File).where(File.model_id == mid, File.file_type == FileType.project)
            )
            .scalars()
            .all()
        )
        if not threemf_files:
            return {"status": "no_3mf"}

        try:
            with tempfile.TemporaryDirectory() as tmp:
                src = threemf_files[0]
                local = Path(tmp) / "model.3mf"
                s3.download_file(settings.s3_bucket_files, src.storage_key, str(local))
                with zipfile.ZipFile(local) as zf:
                    target = None
                    for name in zf.namelist():
                        n = name.lower()
                        if "thumbnail" in n and n.endswith(".png"):
                            target = name
                            break
                    if target is None:
                        return {"status": "no_thumb"}
                    raw = zf.read(target)
                key = f"previews/{model.id}.png"
                s3.put_object(
                    Bucket=settings.s3_bucket_derived,
                    Key=key,
                    Body=io.BytesIO(raw),
                    ContentType="image/png",
                )
                model.preview_storage_key = key
                model.thumbnail_storage_key = key
                model.preview_status = PreviewStatus.extracted_from_3mf
                session.commit()
                return {"status": "ok"}
        except Exception as exc:
            session.rollback()
            log.error("3mf.thumb.fail", model_id=model_id, error=str(exc))
            return {"status": "failed", "error": str(exc)}
