"""Batch import from a meshnest_import_package.zip without full extraction.

Usage (inside api container):
    python -m app.scripts.import_from_zip <zip_path> [limit] [offset]

Reads manifest/models.json/files.csv directly from the zip, then for each
model in models[offset:offset+limit] streams its files from the zip into
MinIO. Commits per-model so progress is durable.

After the slice is processed, kicks STL->GLB / 3MF-thumbnail tasks for new
models and indexes them in Meilisearch (best-effort).
"""
from __future__ import annotations

import csv
import io
import json
import sys
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db_sync import SyncSession
from app.models import (
    File,
    ImportJob,
    Model,
    ModelTag,
)
from app.models._types import (
    FileRole,
    FileType,
    ImportJobStatus,
    ModelStatus,
    PreviewStatus,
    ViewerStatus,
)
from app.services.import_package import (
    _classify,
    _ensure_buckets,
    _s3_client,
    _upsert_category,
    _upsert_tag,
)

log = structlog.get_logger()


def _put_zip_member(
    s3: Any,
    zf: zipfile.ZipFile,
    member: str,
    bucket: str,
    key: str,
    content_type: str | None = None,
) -> int:
    info = zf.getinfo(member)
    with zf.open(info, "r") as src:
        body = src.read()
    kwargs: dict[str, Any] = {"Bucket": bucket, "Key": key, "Body": body}
    if content_type:
        kwargs["ContentType"] = content_type
    s3.put_object(**kwargs)
    return info.file_size


def _import_one_from_zip(
    session: Session,
    s3: Any,
    zf: zipfile.ZipFile,
    job: ImportJob,
    package: dict,
    files_meta: list[dict],
) -> Model:
    new_model_id = uuid.uuid4()
    paths = package.get("paths", {})
    pflags = package.get("print_flags", {}) or {}

    category = _upsert_category(session, package.get("category"))
    tag_objs = [_upsert_tag(session, t) for t in package.get("tags", [])]

    model = Model(
        id=new_model_id,
        slug=package["slug"],
        title=package["title"],
        original_title=package.get("original_title"),
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
    session.flush()

    for t in tag_objs:
        session.add(ModelTag(model_id=model.id, tag_id=t.id))

    has = {"stl": 0, "step": 0, "3mf": 0, "image": 0, "video": 0, "doc": 0}
    for f_meta in files_meta:
        rel = f_meta["relative_path"]
        try:
            zf.getinfo(rel)
        except KeyError:
            log.warning("import.file_missing", path=rel)
            continue
        ext = (f_meta.get("extension") or "").lstrip(".").lower()
        ftype, frole = _classify(ext)
        sub = rel.split("/", 1)[1] if "/" in rel else rel
        storage_key = f"models/{model.id}/{sub}"

        size_bytes = _put_zip_member(s3, zf, rel, settings.s3_bucket_files, storage_key)

        is_primary_raw = f_meta.get("is_primary", "false")
        is_primary = is_primary_raw in ("true", "1", "True")
        sha256 = (f_meta.get("sha256") or "").strip() or None

        session.add(
            File(
                model_id=model.id,
                file_name=f_meta.get("file_name") or sub.rsplit("/", 1)[-1],
                original_file_name=f_meta.get("original_file_name") or sub.rsplit("/", 1)[-1],
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

    if paths.get("preview_image"):
        rel = paths["preview_image"]
        try:
            zf.getinfo(rel)
            suffix = "." + rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
            key = f"previews/{model.id}{suffix}"
            _put_zip_member(s3, zf, rel, settings.s3_bucket_derived, key)
            model.preview_storage_key = key
        except KeyError:
            pass

    if paths.get("thumbnail"):
        rel = paths["thumbnail"]
        try:
            zf.getinfo(rel)
            suffix = "." + rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
            key = f"thumbnails/{model.id}{suffix}"
            _put_zip_member(s3, zf, rel, settings.s3_bucket_derived, key)
            model.thumbnail_storage_key = key
        except KeyError:
            pass

    if paths.get("package_zip"):
        rel = paths["package_zip"]
        try:
            zf.getinfo(rel)
            key = f"packages/{model.id}.zip"
            _put_zip_member(s3, zf, rel, settings.s3_bucket_derived, key)
            model.package_storage_key = key
        except KeyError:
            pass

    session.flush()
    return model


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    zip_path = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) >= 3 else 1
    offset = int(sys.argv[3]) if len(sys.argv) >= 4 else 0

    s3 = _s3_client()
    _ensure_buckets(s3)

    with zipfile.ZipFile(zip_path, "r") as zf:
        manifest = json.loads(zf.read("manifest.json"))
        if manifest.get("format") != "meshnest-import":
            raise SystemExit(f"Unknown format: {manifest.get('format')}")
        if not str(manifest.get("format_version", "")).startswith("1."):
            raise SystemExit(f"Unsupported version: {manifest.get('format_version')}")

        models_json = json.loads(zf.read("database/models.json"))
        files_csv_text = zf.read("database/files.csv").decode("utf-8")
        files_by_model: dict[str, list[dict]] = {}
        for row in csv.DictReader(io.StringIO(files_csv_text)):
            files_by_model.setdefault(row["model_id"], []).append(row)

        all_models = models_json.get("models", [])
        slice_models = all_models[offset : offset + limit]

        print(f"Total in package: {len(all_models)}; importing [{offset}:{offset+limit}] ({len(slice_models)} models)")

        with SyncSession() as session:
            job = ImportJob(
                status=ImportJobStatus.scanning,
                source_type="zip_batch_import",
                source_name=f"offset_{offset}_limit_{limit}",
                started_at=datetime.now(timezone.utc),
            )
            session.add(job)
            session.commit()
            print(f"ImportJob id={job.id}")

            ok = 0
            fail = 0
            for m in slice_models:
                try:
                    _import_one_from_zip(
                        session, s3, zf, job, m, files_by_model.get(m["id"], [])
                    )
                    session.commit()
                    ok += 1
                    print(f"  OK [{ok+fail}/{len(slice_models)}] {m['slug']}")
                except Exception as exc:
                    session.rollback()
                    fail += 1
                    print(f"  FAIL [{ok+fail}/{len(slice_models)}] {m.get('slug')}: {exc}")

            job.models_created = ok
            job.errors_count = fail
            job.finished_at = datetime.now(timezone.utc)
            job.status = (
                ImportJobStatus.completed if fail == 0 else ImportJobStatus.completed_with_warnings
            )
            session.commit()

            from app.tasks.conversion_tasks import extract_3mf_thumbnail, stl_to_glb

            new_models = session.execute(
                select(Model.id, Model.has_stl, Model.has_3mf).where(Model.import_job_id == job.id)
            ).all()
            for mid, has_stl, has_3mf in new_models:
                if has_stl:
                    stl_to_glb.delay(str(mid))
                if has_3mf:
                    extract_3mf_thumbnail.delay(str(mid))

            try:
                from app.services import search as search_svc

                search_svc.ensure_index()
                full_models = (
                    session.execute(
                        select(Model)
                        .options(selectinload(Model.tags), selectinload(Model.category))
                        .where(Model.import_job_id == job.id)
                    )
                    .scalars()
                    .all()
                )
                r = search_svc.index_models(full_models)
                print(f"Meili indexed: {r['indexed']}")
            except Exception as exc:
                print(f"Meili indexing skipped: {exc}")

            print(f"\nDone. job_id={job.id}  ok={ok}  fail={fail}")


if __name__ == "__main__":
    main()
