"""Consume `meshnest_import_package.zip` (format: meshnest-import v1.0).

Шаги:
  1. Скачать zip из bucket `meshnest-imports`
  2. Распаковать в /var/lib/meshnest/imports/{import_job_id}/
  3. Прочитать manifest.json + database/models.json
  4. Для каждой модели:
       - upsert Category, Tag'и
       - INSERT Model
       - upload файлы в bucket `meshnest-files` под `models/{model_id}/...`
       - upload preview/glb/package_zip в bucket `meshnest-derived`
       - INSERT File rows + ModelTag links
  5. Update ImportJob counts/status, kick STL→GLB tasks
"""
from __future__ import annotations

import csv
import io
import json
import shutil
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
import structlog
from botocore.config import Config as BotoConfig
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Category,
    File,
    ImportJob,
    Model,
    ModelTag,
    Tag,
)
from app.models._types import (
    FileRole,
    FileType,
    ImportJobStatus,
    ModelStatus,
    PreviewStatus,
    TagType,
    ViewerStatus,
)

log = structlog.get_logger()


# ---------- helpers (sync S3) ----------

def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key.get_secret_value(),
        aws_secret_access_key=settings.s3_secret_key.get_secret_value(),
        region_name=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
        config=BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def _ensure_buckets(s3) -> None:
    for b in (
        settings.s3_bucket_files,
        settings.s3_bucket_derived,
        settings.s3_bucket_imports,
    ):
        try:
            s3.head_bucket(Bucket=b)
        except Exception:
            s3.create_bucket(Bucket=b)


def _download_to_temp(s3, bucket: str, key: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    s3.download_file(bucket, key, str(dest))


def _upload_file(s3, bucket: str, key: str, src: Path, content_type: str | None = None) -> None:
    extra: dict[str, Any] = {}
    if content_type:
        extra["ContentType"] = content_type
    s3.upload_file(str(src), bucket, key, ExtraArgs=extra)


# ---------- mappers ----------

_BUCKET_BY_EXT = {
    "stl": (FileType.mesh, FileRole.print_file),
    "step": (FileType.cad, FileRole.print_file),
    "stp": (FileType.cad, FileRole.print_file),
    "3mf": (FileType.project, FileRole.print_file),
    "obj": (FileType.mesh, FileRole.source),
    "fbx": (FileType.mesh, FileRole.source),
    "jpg": (FileType.image, FileRole.gallery_image),
    "jpeg": (FileType.image, FileRole.gallery_image),
    "png": (FileType.image, FileRole.gallery_image),
    "webp": (FileType.image, FileRole.gallery_image),
    "bmp": (FileType.image, FileRole.gallery_image),
    "mp4": (FileType.video, FileRole.video),
    "mov": (FileType.video, FileRole.video),
    "webm": (FileType.video, FileRole.video),
    "txt": (FileType.document, FileRole.instruction),
    "md": (FileType.document, FileRole.instruction),
    "pdf": (FileType.document, FileRole.instruction),
    "zip": (FileType.archive, FileRole.nested_archive),
    "rar": (FileType.archive, FileRole.nested_archive),
}


def _classify(ext: str) -> tuple[FileType, FileRole]:
    return _BUCKET_BY_EXT.get(ext.lower().lstrip("."), (FileType.other, FileRole.other))


def _upsert_category(session: Session, path: str | None) -> Category | None:
    if not path or path == "uncategorized":
        path = "uncategorized"
    existing = session.execute(select(Category).where(Category.path == path)).scalar_one_or_none()
    if existing:
        return existing

    parts = path.split("/")
    parent = None
    accumulated = ""
    cat: Category | None = None
    for i, part in enumerate(parts):
        accumulated = "/".join(parts[: i + 1])
        cat = session.execute(
            select(Category).where(Category.path == accumulated)
        ).scalar_one_or_none()
        if cat is None:
            cat = Category(
                slug=part,
                name=part.replace("_", " ").title(),
                path=accumulated,
                parent_id=parent.id if parent else None,
                sort_order=i,
            )
            session.add(cat)
            session.flush()
        parent = cat
    return cat


def _upsert_tag(session: Session, slug: str) -> Tag:
    existing = session.execute(select(Tag).where(Tag.slug == slug)).scalar_one_or_none()
    if existing:
        return existing
    t_type = TagType.topic
    if slug.startswith("has-") or slug.startswith("source-"):
        t_type = TagType.status
    elif slug in ("flexi", "articulated", "print-in-place", "bambu-3mf", "multicolor", "no-support"):
        t_type = TagType.print
    elif slug in ("multipart", "single-part", "assembly", "duplicate-detected",
                  "needs-review", "loose-file", "nested-archive", "multi-model-suspect"):
        t_type = TagType.technical
    tag = Tag(slug=slug, name=slug.replace("-", " ").title(), type=t_type)
    session.add(tag)
    session.flush()
    return tag


# ---------- main importer ----------

def process_import_package_sync(
    session: Session,
    import_job_id: uuid.UUID,
    package_storage_key: str,
) -> dict[str, int]:
    """Run import. Возвращает summary (models, files, warnings)."""
    job: ImportJob | None = session.get(ImportJob, import_job_id)
    if job is None:
        raise RuntimeError(f"ImportJob {import_job_id} not found")

    job.status = ImportJobStatus.extracting
    job.started_at = datetime.now(timezone.utc)
    session.flush()

    s3 = _s3_client()
    _ensure_buckets(s3)

    workdir = Path(tempfile.mkdtemp(prefix=f"meshnest-import-{import_job_id}-"))
    log.info("import.start", job=str(import_job_id), workdir=str(workdir))

    try:
        # 1. download
        local_zip = workdir / "package.zip"
        _download_to_temp(s3, settings.s3_bucket_imports, package_storage_key, local_zip)

        # 2. extract
        extract_dir = workdir / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(local_zip, "r") as zf:
            zf.extractall(extract_dir)

        # 3. validate manifest
        manifest_path = extract_dir / "manifest.json"
        if not manifest_path.exists():
            raise RuntimeError("manifest.json missing in package")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("format") != "meshnest-import":
            raise RuntimeError(f"Unknown format: {manifest.get('format')}")
        if not manifest.get("format_version", "").startswith("1."):
            raise RuntimeError(f"Unsupported version: {manifest.get('format_version')}")

        # 4. read models.json + files.csv
        models_json = json.loads((extract_dir / "database" / "models.json").read_text(encoding="utf-8"))
        files_csv_path = extract_dir / "database" / "files.csv"
        files_by_model: dict[str, list[dict]] = {}
        if files_csv_path.exists():
            with files_csv_path.open("r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    files_by_model.setdefault(row["model_id"], []).append(row)

        job.status = ImportJobStatus.scanning
        session.flush()

        # 5. import each model
        models_created = 0
        files_processed = 0
        warnings: list[str] = []

        for m in models_json.get("models", []):
            try:
                _import_one_model(
                    session=session,
                    s3=s3,
                    job=job,
                    extract_root=extract_dir,
                    package=m,
                    files_meta=files_by_model.get(m["id"], []),
                )
                models_created += 1
                files_processed += len(files_by_model.get(m["id"], []))
            except Exception as exc:
                msg = f"model {m.get('id')}: {exc}"
                warnings.append(msg)
                log.warning("import.model_failed", error=msg)

            if models_created % 50 == 0:
                job.models_created = models_created
                job.files_processed = files_processed
                pct = int(100 * models_created / max(1, len(models_json.get("models", []))))
                job.progress_pct = min(95, pct)
                session.flush()

        job.models_created = models_created
        job.files_processed = files_processed
        job.warnings_count = len(warnings)
        job.progress_pct = 100
        job.status = (
            ImportJobStatus.completed_with_warnings
            if warnings
            else ImportJobStatus.completed
        )
        job.finished_at = datetime.now(timezone.utc)
        if warnings:
            job.error_message = "\n".join(warnings[:50])
        session.flush()

        log.info(
            "import.done",
            models=models_created,
            files=files_processed,
            warnings=len(warnings),
        )
        return {
            "models": models_created,
            "files": files_processed,
            "warnings": len(warnings),
        }
    except Exception as exc:
        job.status = ImportJobStatus.failed
        job.error_message = str(exc)
        job.finished_at = datetime.now(timezone.utc)
        session.flush()
        log.error("import.failed", error=str(exc))
        raise
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _import_one_model(
    *,
    session: Session,
    s3: Any,
    job: ImportJob,
    extract_root: Path,
    package: dict,
    files_meta: list[dict],
) -> Model:
    new_model_id = uuid.uuid4()
    paths = package.get("paths", {})
    model_folder = paths.get("model_folder")
    if not model_folder:
        raise RuntimeError("missing paths.model_folder")
    model_folder_abs = (extract_root / model_folder).resolve()
    if not model_folder_abs.exists():
        raise RuntimeError(f"model folder not found: {model_folder}")

    category = _upsert_category(session, package.get("category"))
    tag_objs = [_upsert_tag(session, t) for t in package.get("tags", [])]

    pflags = package.get("print_flags", {}) or {}

    model = Model(
        id=new_model_id,
        slug=package["slug"],
        title=package["title"],
        original_title=package.get("original_title"),
        description=None,
        category_id=category.id if category else None,
        category_confidence=package.get("category_confidence"),
        status=ModelStatus.needs_review,
        is_reviewed=False,
        is_flexi=bool(pflags.get("is_flexi")),
        is_print_in_place=bool(pflags.get("is_print_in_place")),
        is_multipart=bool(pflags.get("is_multipart")),
        is_assembly=bool(pflags.get("is_assembly")),
        viewer_status=ViewerStatus(package.get("viewer_status", "pending")),
        preview_status=PreviewStatus(package.get("preview_status", "pending")),
        source_type=package.get("source_type"),
        source_name=package.get("source_archive_ref") or package.get("source_name"),
        import_job_id=job.id,
        imported_at=datetime.now(timezone.utc),
    )
    session.add(model)
    session.flush()  # получить ID

    # m2m tags
    for t in tag_objs:
        session.add(ModelTag(model_id=model.id, tag_id=t.id))

    # Upload файлов модели
    has = {"stl": 0, "step": 0, "3mf": 0, "image": 0, "video": 0, "doc": 0}
    for f_meta in files_meta:
        rel = f_meta["relative_path"]
        local_path = (extract_root / rel).resolve()
        if not local_path.exists():
            log.warning("import.file_missing", path=rel)
            continue
        ext = (f_meta.get("extension") or "").lstrip(".").lower()
        ftype, frole = _classify(ext)
        storage_key = f"models/{model.id}/{rel.split('/', 1)[1] if '/' in rel else rel}"
        # rel под organizer'ом начинается с models/{cat}/{slug}/... — обрезаем для чистоты ключа

        _upload_file(s3, settings.s3_bucket_files, storage_key, local_path)

        is_primary = bool(int(f_meta.get("is_primary", "false") in ("true", "1", "True")))
        size_bytes = int(f_meta.get("size_bytes") or local_path.stat().st_size)
        sha256 = (f_meta.get("sha256") or "").strip() or None

        session.add(
            File(
                model_id=model.id,
                file_name=f_meta.get("file_name") or local_path.name,
                original_file_name=f_meta.get("original_file_name") or local_path.name,
                extension=f".{ext}" if ext else None,
                file_type=ftype,
                role=frole,
                storage_key=storage_key,
                size_bytes=size_bytes,
                sha256=sha256,
                is_primary=is_primary,
            )
        )

        if ftype == FileType.mesh and ext == "stl":
            has["stl"] += 1
        elif ftype == FileType.cad:
            has["step"] += 1
        elif ftype == FileType.project and ext == "3mf":
            has["3mf"] += 1
        elif ftype == FileType.image:
            has["image"] += 1
        elif ftype == FileType.video:
            has["video"] += 1
        elif ftype == FileType.document:
            has["doc"] += 1

    # Counters denormalized
    model.stl_count = has["stl"]
    model.step_count = has["step"]
    model.three_mf_count = has["3mf"]
    model.image_count = has["image"]
    model.video_count = has["video"]
    model.document_count = has["doc"]
    model.has_stl = has["stl"] > 0
    model.has_step = has["step"] > 0
    model.has_3mf = has["3mf"] > 0
    model.has_images = has["image"] > 0
    model.has_video = has["video"] > 0

    # Preview / thumbnail / package zip → derived bucket
    if paths.get("preview_image"):
        local = (extract_root / paths["preview_image"]).resolve()
        if local.exists():
            key = f"previews/{model.id}{local.suffix}"
            _upload_file(s3, settings.s3_bucket_derived, key, local)
            model.preview_storage_key = key
    if paths.get("thumbnail"):
        local = (extract_root / paths["thumbnail"]).resolve()
        if local.exists():
            key = f"thumbnails/{model.id}{local.suffix}"
            _upload_file(s3, settings.s3_bucket_derived, key, local)
            model.thumbnail_storage_key = key
    if paths.get("package_zip"):
        local = (extract_root / paths["package_zip"]).resolve()
        if local.exists():
            key = f"packages/{model.id}.zip"
            _upload_file(s3, settings.s3_bucket_derived, key, local)
            model.package_storage_key = key

    session.flush()
    return model
