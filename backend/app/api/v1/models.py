"""GET /models, GET /models/{id_or_slug}, GET /models/{id_or_slug}/files,
   GET /models/{id_or_slug}/preview|glb|download,
   POST /models, POST /models/{id}/files,
   POST /models/{id}/mark-reviewed."""
from datetime import datetime, timezone
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File as FastFile, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse
from slugify import slugify
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db import get_db
from app.deps import CurrentUser, require_contributor
from app.models import Category, File, Model, ModelTag, Tag, User
from app.models._types import (
    FileRole,
    FileType,
    ModelStatus,
    PreviewStatus,
    TagType,
    ViewerStatus,
)
from app.schemas.models import (
    FileItem,
    ModelCard,
    ModelDetail,
    ModelListResponse,
)
from app.services.storage import get_storage


_EXT_MAP = {
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


def _classify_ext(ext: str) -> tuple[FileType, FileRole]:
    return _EXT_MAP.get(ext.lstrip(".").lower(), (FileType.other, FileRole.other))


async def _upsert_category_async(session: AsyncSession, path: str | None) -> Category | None:
    if not path or path == "uncategorized":
        path = "uncategorized"
    existing = (await session.execute(select(Category).where(Category.path == path))).scalar_one_or_none()
    if existing:
        return existing
    parts = path.split("/")
    parent: Category | None = None
    cat: Category | None = None
    for i, part in enumerate(parts):
        accumulated = "/".join(parts[: i + 1])
        cat = (await session.execute(select(Category).where(Category.path == accumulated))).scalar_one_or_none()
        if cat is None:
            cat = Category(
                slug=part,
                name=part.replace("_", " ").title(),
                path=accumulated,
                parent_id=parent.id if parent else None,
                sort_order=i,
            )
            session.add(cat)
            await session.flush()
        parent = cat
    return cat


async def _upsert_tag_async(session: AsyncSession, slug: str) -> Tag:
    existing = (await session.execute(select(Tag).where(Tag.slug == slug))).scalar_one_or_none()
    if existing:
        return existing
    tag = Tag(slug=slug, name=slug.replace("-", " ").title(), type=TagType.topic)
    session.add(tag)
    await session.flush()
    return tag


async def _unique_slug(session: AsyncSession, base: str) -> str:
    slug = base or f"model-{uuid.uuid4().hex[:8]}"
    n = 1
    while True:
        existing = (
            await session.execute(select(Model.id).where(Model.slug == slug))
        ).scalar_one_or_none()
        if existing is None:
            return slug
        n += 1
        slug = f"{base}-{n}"

router = APIRouter()


def _category_path(model: Model) -> str | None:
    return model.category.path if model.category else None


_FILE_TYPE_PRIORITY = {
    "image": 0,     # gallery_images first
    "project": 1,   # 3MF (often has nice embedded thumb)
    "mesh": 2,      # STL/OBJ
    "cad": 3,       # STEP — likely no thumb yet
    "document": 4,
    "other": 5,
}

_THUMB_LIMIT_PER_CARD = 6


async def _build_card(model: Model, files: list[File] | None = None) -> ModelCard:
    storage = get_storage()
    preview_url: str | None = None
    if model.preview_storage_key:
        preview_url = await storage.presign_get(
            settings.s3_bucket_derived, model.preview_storage_key, settings.s3_presigned_ttl
        )

    # Collect carousel thumbnails: prefer image files, then 3MF, then mesh.
    thumbnails: list[str] = []
    if files:
        ranked = sorted(
            files,
            key=lambda f: (
                _FILE_TYPE_PRIORITY.get(f.file_type.value, 99),
                0 if f.is_primary else 1,
                f.file_name,
            ),
        )
        for f in ranked[:_THUMB_LIMIT_PER_CARD]:
            ext = (f.extension or "").lstrip(".").lower()
            is_thumbable = (
                (f.file_type.value == "image" and ext in ("jpg", "jpeg", "png", "webp", "bmp"))
                or (f.file_type.value == "project" and ext == "3mf")
                or (f.file_type.value == "mesh" and ext in ("stl", "obj", "fbx"))
            )
            if not is_thumbable:
                continue
            url = await storage.presign_get(
                settings.s3_bucket_derived,
                f"thumbs/{f.id}.png",
                settings.s3_presigned_ttl,
            )
            thumbnails.append(url)

    return ModelCard(
        id=model.id,
        slug=model.slug,
        title=model.title,
        category_path=_category_path(model),
        tags=[t.slug for t in model.tags],
        preview_url=preview_url,
        thumbnails=thumbnails,
        has_stl=model.has_stl,
        has_step=model.has_step,
        has_3mf=model.has_3mf,
        has_images=model.has_images,
        has_video=model.has_video,
        is_flexi=model.is_flexi,
        is_print_in_place=model.is_print_in_place,
        is_multipart=model.is_multipart,
        is_reviewed=model.is_reviewed,
        status=model.status,
        file_count=model.stl_count + model.step_count + model.three_mf_count
                   + model.image_count + model.video_count + model.document_count,
    )


async def _resolve_model(
    session: AsyncSession, id_or_slug: str
) -> Model:
    try:
        as_uuid = uuid.UUID(id_or_slug)
        stmt = (
            select(Model)
            .where(Model.id == as_uuid)
            .options(selectinload(Model.category), selectinload(Model.tags))
        )
    except ValueError:
        stmt = (
            select(Model)
            .where(Model.slug == id_or_slug)
            .options(selectinload(Model.category), selectinload(Model.tags))
        )
    result = await session.execute(stmt)
    model = result.scalar_one_or_none()
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Model not found")
    return model


@router.get("/models", response_model=ModelListResponse)
async def list_models(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
    category: str | None = Query(None, description="category path or slug"),
    tag: list[str] | None = Query(None, description="tag slug; multiple = AND"),
    has_stl: bool | None = Query(None),
    has_3mf: bool | None = Query(None),
    has_step: bool | None = Query(None),
    is_flexi: bool | None = Query(None),
    reviewed: bool | None = Query(None),
    needs_review: bool | None = Query(None),
    q: str | None = Query(None, max_length=200),
    page: int = Query(1, ge=1),
    page_size: int = Query(48, ge=1, le=200),
    sort: str = Query("imported_desc"),
) -> ModelListResponse:
    base = select(Model).options(
        selectinload(Model.category),
        selectinload(Model.tags),
    )

    if category:
        cat_stmt = select(Category.id).where(
            (Category.path == category) | (Category.slug == category)
        )
        cat_id = (await session.execute(cat_stmt)).scalar_one_or_none()
        if cat_id is None:
            return ModelListResponse(items=[], total=0, page=page, page_size=page_size)
        base = base.where(Model.category_id == cat_id)

    if has_stl is not None:
        base = base.where(Model.has_stl == has_stl)
    if has_3mf is not None:
        base = base.where(Model.has_3mf == has_3mf)
    if has_step is not None:
        base = base.where(Model.has_step == has_step)
    if is_flexi is not None:
        base = base.where(Model.is_flexi == is_flexi)
    if reviewed is True:
        base = base.where(Model.is_reviewed.is_(True))
    if needs_review is True:
        base = base.where(Model.status == ModelStatus.needs_review)
    if q:
        like = f"%{q.lower()}%"
        base = base.where(func.lower(Model.title).like(like))

    if tag:
        from app.models import ModelTag, Tag

        for tslug in tag:
            sub = (
                select(ModelTag.model_id)
                .join(Tag, Tag.id == ModelTag.tag_id)
                .where(Tag.slug == tslug)
            )
            base = base.where(Model.id.in_(sub))

    # total
    total = (await session.execute(select(func.count()).select_from(base.subquery()))).scalar_one()

    # sort
    if sort == "imported_asc":
        base = base.order_by(Model.imported_at.asc().nulls_last())
    elif sort == "title_asc":
        base = base.order_by(Model.title.asc())
    elif sort == "title_desc":
        base = base.order_by(Model.title.desc())
    else:
        base = base.order_by(desc(Model.imported_at), desc(Model.created_at))

    base = base.offset((page - 1) * page_size).limit(page_size)
    base = base.options(selectinload(Model.files))
    rows = (await session.execute(base)).scalars().all()
    items = [await _build_card(m, m.files) for m in rows]
    return ModelListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/models/{id_or_slug}", response_model=ModelDetail)
async def get_model(
    id_or_slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
) -> ModelDetail:
    model = await _resolve_model(session, id_or_slug)
    files = (
        await session.execute(
            select(File).where(File.model_id == model.id)
        )
    ).scalars().all()
    card = await _build_card(model, files)
    return ModelDetail(
        **card.model_dump(),
        original_title=model.original_title,
        description=model.description,
        category_id=model.category_id,
        category_confidence=model.category_confidence,
        is_assembly=model.is_assembly,
        preview_status=model.preview_status,
        viewer_status=model.viewer_status,
        source_type=model.source_type,
        source_name=model.source_name,
        source_hash=model.source_hash,
        stl_count=model.stl_count,
        step_count=model.step_count,
        three_mf_count=model.three_mf_count,
        image_count=model.image_count,
        video_count=model.video_count,
        document_count=model.document_count,
        created_at=model.created_at,
        updated_at=model.updated_at,
        imported_at=model.imported_at,
    )


@router.get("/models/{id_or_slug}/files", response_model=list[FileItem])
async def list_model_files(
    id_or_slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
) -> list[FileItem]:
    model = await _resolve_model(session, id_or_slug)
    files = (
        await session.execute(
            select(File).where(File.model_id == model.id).order_by(File.role, File.file_name)
        )
    ).scalars().all()
    storage = get_storage()
    out: list[FileItem] = []
    for f in files:
        download_url = await storage.presign_get(
            settings.s3_bucket_files, f.storage_key, settings.s3_presigned_ttl
        )
        ext = (f.extension or "").lstrip(".").lower()
        thumbnail_url: str | None = None
        viewer_url: str | None = None
        if (f.file_type.value == "image" and ext in ("jpg", "jpeg", "png", "webp", "bmp")) \
                or (f.file_type.value == "project" and ext == "3mf") \
                or (f.file_type.value == "mesh" and ext in ("stl", "obj", "fbx")):
            thumbnail_url = await storage.presign_get(
                settings.s3_bucket_derived,
                f"thumbs/{f.id}.png",
                settings.s3_presigned_ttl,
            )
        if f.file_type.value == "mesh" and ext in ("stl", "obj", "fbx"):
            viewer_url = await storage.presign_get(
                settings.s3_bucket_derived,
                f"glb/{f.id}.glb",
                settings.s3_presigned_ttl,
            )
        out.append(
            FileItem(
                id=f.id,
                file_name=f.file_name,
                extension=f.extension,
                file_type=f.file_type,
                role=f.role,
                size_bytes=f.size_bytes,
                sha256=f.sha256,
                is_primary=f.is_primary,
                download_url=download_url,
                thumbnail_url=thumbnail_url,
                viewer_url=viewer_url,
            )
        )
    return out


@router.get("/models/{id_or_slug}/preview")
async def get_model_preview(
    id_or_slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
) -> RedirectResponse:
    model = await _resolve_model(session, id_or_slug)
    if not model.preview_storage_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No preview")
    url = await get_storage().presign_get(
        settings.s3_bucket_derived, model.preview_storage_key, settings.s3_presigned_ttl
    )
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get("/models/{id_or_slug}/glb")
async def get_model_glb(
    id_or_slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
) -> RedirectResponse:
    model = await _resolve_model(session, id_or_slug)
    if not model.viewer_storage_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "GLB not yet ready")
    url = await get_storage().presign_get(
        settings.s3_bucket_derived, model.viewer_storage_key, settings.s3_presigned_ttl
    )
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get("/models/{id_or_slug}/download")
async def download_model_zip(
    id_or_slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
) -> RedirectResponse:
    model = await _resolve_model(session, id_or_slug)
    if not model.package_storage_key:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Per-model ZIP not available")
    url = await get_storage().presign_get(
        settings.s3_bucket_derived, model.package_storage_key, settings.s3_presigned_ttl
    )
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


def _normalize_uploads(uploads: list[UploadFile]) -> list[tuple[str, bytes, str | None]]:
    """Flatten an upload list into [(name, bytes, content_type)].

    If the only file is a .zip, transparently unpack it: every member
    becomes its own logical file in the model. 3MF files (also zips)
    are *not* unpacked — they are first-class print files. Nested
    zips inside the dropped archive are kept as archive entries.
    """
    import zipfile
    from io import BytesIO

    if (
        len(uploads) == 1
        and uploads[0].filename
        and uploads[0].filename.lower().endswith(".zip")
    ):
        u = uploads[0]
        u.file.seek(0)
        items: list[tuple[str, bytes, str | None]] = []
        with zipfile.ZipFile(u.file, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                base = info.filename.replace("\\", "/").rsplit("/", 1)[-1]
                if not base or base.startswith("."):
                    continue
                with zf.open(info, "r") as src:
                    data = src.read()
                items.append((base, data, None))
        return items

    out: list[tuple[str, bytes, str | None]] = []
    for u in uploads:
        if not u.filename:
            continue
        u.file.seek(0)
        data = u.file.read()
        out.append((u.filename, data, u.content_type))
    return out


async def _upload_files_to_model(
    session: AsyncSession,
    model: Model,
    uploads: list[UploadFile],
) -> list[tuple[uuid.UUID, str, str]]:
    """Upload files into MinIO + insert File rows. Returns [(file_id, file_type, ext)]."""
    storage = get_storage()
    new_file_ids: list[tuple[uuid.UUID, str, str]] = []
    has = {"stl": 0, "step": 0, "3mf": 0, "image": 0, "video": 0, "doc": 0}

    items = _normalize_uploads(uploads)
    for name, data, content_type in items:
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        ftype, frole = _classify_ext(ext)
        file_id = uuid.uuid4()
        clean_name = name.replace("\\", "/").rsplit("/", 1)[-1]
        storage_key = f"models/{model.id}/{file_id}/{clean_name}"
        size = len(data)

        await storage.put_bytes(
            settings.s3_bucket_files,
            storage_key,
            data,
            content_type=content_type,
        )

        session.add(
            File(
                id=file_id,
                model_id=model.id,
                file_name=clean_name,
                original_file_name=clean_name,
                extension=f".{ext}" if ext else None,
                file_type=ftype,
                role=frole,
                storage_key=storage_key,
                size_bytes=size,
                is_primary=False,
            )
        )
        new_file_ids.append((file_id, ftype.value, ext))

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

    # Update denormalized counts (incrementally)
    model.stl_count += has["stl"]
    model.step_count += has["step"]
    model.three_mf_count += has["3mf"]
    model.image_count += has["image"]
    model.video_count += has["video"]
    model.document_count += has["doc"]
    if has["stl"] > 0:
        model.has_stl = True
    if has["step"] > 0:
        model.has_step = True
    if has["3mf"] > 0:
        model.has_3mf = True
    if has["image"] > 0:
        model.has_images = True
    if has["video"] > 0:
        model.has_video = True

    await session.flush()
    return new_file_ids


def _kick_file_tasks(new_file_ids: list[tuple[uuid.UUID, str, str]]) -> None:
    from app.tasks.conversion_tasks import generate_file_thumbnail, stl_to_glb_per_file

    for fid, ftype_val, ext in new_file_ids:
        is_thumbable = (
            (ftype_val == "mesh" and ext in ("stl", "obj", "fbx"))
            or (ftype_val == "project" and ext == "3mf")
            or (ftype_val == "image" and ext in ("jpg", "jpeg", "png", "webp", "bmp"))
        )
        if is_thumbable:
            generate_file_thumbnail.delay(str(fid))
        if ftype_val == "mesh" and ext in ("stl", "obj", "fbx"):
            stl_to_glb_per_file.delay(str(fid))


@router.post("/models", response_model=ModelDetail, status_code=status.HTTP_201_CREATED)
async def create_model(
    title: str = Form(..., min_length=1, max_length=255),
    category: str | None = Form(None),
    tags: str | None = Form(None),
    files: list[UploadFile] = FastFile(default_factory=list),
    user: User = Depends(require_contributor),
    session: AsyncSession = Depends(get_db),
) -> ModelDetail:
    base_slug = slugify(title) or f"model-{uuid.uuid4().hex[:8]}"
    slug = await _unique_slug(session, base_slug)

    cat = await _upsert_category_async(session, category)
    tag_slugs = [
        slugify(t.strip()) for t in (tags or "").split(",") if t.strip()
    ] if tags else []
    tag_objs = [await _upsert_tag_async(session, s) for s in tag_slugs]

    model = Model(
        slug=slug,
        title=title,
        category_id=cat.id if cat else None,
        status=ModelStatus.needs_review,
        viewer_status=ViewerStatus.pending,
        preview_status=PreviewStatus.pending,
        uploaded_by=user.id,
        imported_at=datetime.now(timezone.utc),
        source_type="manual_upload",
    )
    session.add(model)
    await session.flush()
    for t in tag_objs:
        session.add(ModelTag(model_id=model.id, tag_id=t.id))

    new_file_ids = await _upload_files_to_model(session, model, files)
    await session.commit()
    _kick_file_tasks(new_file_ids)

    # Refresh with relations for the response
    refreshed = await _resolve_model(session, str(model.id))
    refreshed_files = (
        await session.execute(select(File).where(File.model_id == model.id))
    ).scalars().all()
    card = await _build_card(refreshed, refreshed_files)
    return ModelDetail(
        **card.model_dump(),
        original_title=refreshed.original_title,
        description=refreshed.description,
        category_id=refreshed.category_id,
        category_confidence=refreshed.category_confidence,
        is_assembly=refreshed.is_assembly,
        preview_status=refreshed.preview_status,
        viewer_status=refreshed.viewer_status,
        source_type=refreshed.source_type,
        source_name=refreshed.source_name,
        source_hash=refreshed.source_hash,
        stl_count=refreshed.stl_count,
        step_count=refreshed.step_count,
        three_mf_count=refreshed.three_mf_count,
        image_count=refreshed.image_count,
        video_count=refreshed.video_count,
        document_count=refreshed.document_count,
        created_at=refreshed.created_at,
        updated_at=refreshed.updated_at,
        imported_at=refreshed.imported_at,
    )


@router.post("/models/{id_or_slug}/files", response_model=ModelDetail)
async def add_files_to_model(
    id_or_slug: str,
    files: list[UploadFile] = FastFile(...),
    _user: User = Depends(require_contributor),
    session: AsyncSession = Depends(get_db),
) -> ModelDetail:
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no files")
    model = await _resolve_model(session, id_or_slug)
    new_file_ids = await _upload_files_to_model(session, model, files)
    await session.commit()
    _kick_file_tasks(new_file_ids)

    refreshed = await _resolve_model(session, id_or_slug)
    refreshed_files = (
        await session.execute(select(File).where(File.model_id == model.id))
    ).scalars().all()
    card = await _build_card(refreshed, refreshed_files)
    return ModelDetail(
        **card.model_dump(),
        original_title=refreshed.original_title,
        description=refreshed.description,
        category_id=refreshed.category_id,
        category_confidence=refreshed.category_confidence,
        is_assembly=refreshed.is_assembly,
        preview_status=refreshed.preview_status,
        viewer_status=refreshed.viewer_status,
        source_type=refreshed.source_type,
        source_name=refreshed.source_name,
        source_hash=refreshed.source_hash,
        stl_count=refreshed.stl_count,
        step_count=refreshed.step_count,
        three_mf_count=refreshed.three_mf_count,
        image_count=refreshed.image_count,
        video_count=refreshed.video_count,
        document_count=refreshed.document_count,
        created_at=refreshed.created_at,
        updated_at=refreshed.updated_at,
        imported_at=refreshed.imported_at,
    )


@router.post("/models/{id_or_slug}/mark-reviewed", response_model=ModelDetail)
async def mark_reviewed(
    id_or_slug: str,
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: Annotated[Model, Depends(require_contributor)],
) -> ModelDetail:
    model = await _resolve_model(session, id_or_slug)
    model.is_reviewed = True
    if model.status == ModelStatus.needs_review:
        model.status = ModelStatus.ready
    await session.flush()
    card = await _build_card(model)
    return ModelDetail(
        **card.model_dump(),
        original_title=model.original_title,
        description=model.description,
        category_id=model.category_id,
        category_confidence=model.category_confidence,
        is_assembly=model.is_assembly,
        preview_status=model.preview_status,
        viewer_status=model.viewer_status,
        source_type=model.source_type,
        source_name=model.source_name,
        source_hash=model.source_hash,
        stl_count=model.stl_count,
        step_count=model.step_count,
        three_mf_count=model.three_mf_count,
        image_count=model.image_count,
        video_count=model.video_count,
        document_count=model.document_count,
        created_at=model.created_at,
        updated_at=model.updated_at,
        imported_at=model.imported_at,
    )
