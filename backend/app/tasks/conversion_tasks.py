"""Celery tasks: STL → GLB, 3MF thumbnail extraction, per-file thumbnail render."""
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


# ---------- per-file STL → GLB (multi-mesh support) ----------

@celery_app.task(name="app.tasks.conversion_tasks.stl_to_glb_per_file", max_retries=1)
def stl_to_glb_per_file(file_id: str) -> dict:
    """Convert a single mesh file to GLB stored at derived/glb/{file_id}.glb.

    Used to populate the per-file viewer carousel; the model-level
    viewer_storage_key is also set on the first file we successfully
    convert (so the Model detail page works even before the file index
    loads).
    """
    fid = uuid.UUID(file_id)
    s3 = _s3()
    with SyncSession() as session:
        f = session.get(File, fid)
        if f is None or f.file_type != FileType.mesh:
            return {"status": "skip"}
        ext = (f.extension or "").lstrip(".").lower()
        if ext not in ("stl", "obj", "fbx"):
            return {"status": "skip"}

        glb_key = f"glb/{file_id}.glb"
        try:
            with tempfile.TemporaryDirectory() as tmp:
                local = Path(tmp) / f"src.{ext}"
                glb_local = Path(tmp) / "out.glb"
                s3.download_file(settings.s3_bucket_files, f.storage_key, str(local))
                mesh = trimesh.load(local, force="mesh")
                if isinstance(mesh, trimesh.Trimesh):
                    scene = trimesh.Scene([mesh])
                elif isinstance(mesh, trimesh.Scene):
                    scene = mesh
                else:
                    raise RuntimeError(f"Unsupported trimesh type: {type(mesh)}")
                scene.export(file_obj=str(glb_local), file_type="glb")
                s3.upload_file(
                    str(glb_local),
                    settings.s3_bucket_derived,
                    glb_key,
                    ExtraArgs={"ContentType": "model/gltf-binary"},
                )

            # Promote to model-level viewer if not already set
            model = session.get(Model, f.model_id)
            if model is not None and not model.viewer_storage_key:
                model.viewer_storage_key = glb_key
                model.viewer_status = ViewerStatus.glb_ready
                session.commit()

            log.info("file.glb.ok", file_id=file_id, key=glb_key)
            return {"status": "ok", "key": glb_key}
        except Exception as exc:
            log.error("file.glb.fail", file_id=file_id, error=str(exc))
            return {"status": "failed", "error": str(exc)}


# ---------- legacy model-level STL → GLB ----------

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


# ---------- 3MF model-level thumbnail (legacy) ----------

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


# ---------- per-file thumbnail render (mesh / image / 3MF) ----------

THUMB_SIZE = (800, 600)


def _render_mesh_thumbnail(local_mesh_path: Path, out_png: Path, size: tuple[int, int]) -> None:
    """Headless mesh → PNG via numpy orthographic projection + Pillow shaded triangles.

    No OpenGL, no display server needed. Quality is approximate (no anti-aliasing,
    no shadows) but good enough for a 800x600 gallery thumbnail.
    """
    import numpy as np
    from PIL import Image, ImageDraw

    mesh = trimesh.load(local_mesh_path, force="mesh")
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)
    if not isinstance(mesh, trimesh.Trimesh):
        raise RuntimeError(f"Unsupported trimesh type: {type(mesh)}")

    verts = np.asarray(mesh.vertices, dtype=np.float64)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    if len(verts) == 0 or len(faces) == 0:
        raise RuntimeError("empty mesh")

    # center
    bbox_min = verts.min(axis=0)
    bbox_max = verts.max(axis=0)
    center = (bbox_min + bbox_max) / 2.0
    verts = verts - center

    # isometric-ish camera
    ax = np.deg2rad(25.0)
    ay = np.deg2rad(35.0)
    Rx = np.array([[1, 0, 0], [0, np.cos(ax), -np.sin(ax)], [0, np.sin(ax), np.cos(ax)]])
    Ry = np.array([[np.cos(ay), 0, np.sin(ay)], [0, 1, 0], [-np.sin(ay), 0, np.cos(ay)]])
    R = Rx @ Ry
    cam = verts @ R.T

    # face normals + shading in camera space
    v0 = cam[faces[:, 0]]
    v1 = cam[faces[:, 1]]
    v2 = cam[faces[:, 2]]
    n = np.cross(v1 - v0, v2 - v0)
    nl = np.linalg.norm(n, axis=1, keepdims=True)
    nl[nl == 0] = 1.0
    n = n / nl
    light = np.array([0.4, 0.5, 1.0])
    light = light / np.linalg.norm(light)
    intensity = np.clip(n @ light, 0.0, 1.0)

    # back-to-front sort
    face_z = cam[faces][:, :, 2].mean(axis=1)
    order = np.argsort(face_z)

    # scale to image
    pts2d = cam[:, :2]
    mn = pts2d.min(axis=0)
    mx = pts2d.max(axis=0)
    span = mx - mn
    if span[0] <= 0:
        span[0] = 1e-6
    if span[1] <= 0:
        span[1] = 1e-6
    margin = 30
    avail_w = size[0] - 2 * margin
    avail_h = size[1] - 2 * margin
    scale = min(avail_w / span[0], avail_h / span[1])
    px = (pts2d - mn) * scale
    # center image and flip Y
    off_x = (size[0] - span[0] * scale) / 2.0
    off_y = (size[1] - span[1] * scale) / 2.0
    px_x = px[:, 0] + off_x
    px_y = size[1] - (px[:, 1] + off_y)
    pts_img = np.stack([px_x, px_y], axis=1)

    img = Image.new("RGB", size, (245, 246, 248))
    draw = ImageDraw.Draw(img)
    base_r, base_g, base_b = 96, 130, 180  # subtle blue-grey
    for i in order:
        f = faces[i]
        c = float(intensity[i])
        r = int(40 + c * (base_r - 40))
        g = int(50 + c * (base_g - 50))
        b = int(70 + c * (base_b - 70))
        pts = [tuple(pts_img[v]) for v in f]
        draw.polygon(pts, fill=(r, g, b))

    img.save(out_png, "PNG", optimize=True)


def _resize_image_to_thumb(local_img_path: Path, out_png: Path, size: tuple[int, int]) -> None:
    from PIL import Image

    with Image.open(local_img_path) as im:
        im = im.convert("RGB")
        im.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, (245, 246, 248))
        ox = (size[0] - im.width) // 2
        oy = (size[1] - im.height) // 2
        canvas.paste(im, (ox, oy))
        canvas.save(out_png, "PNG", optimize=True)


def _extract_3mf_embedded(local_3mf_path: Path, out_png: Path, size: tuple[int, int]) -> bool:
    from PIL import Image

    with zipfile.ZipFile(local_3mf_path) as zf:
        target = None
        for name in zf.namelist():
            n = name.lower()
            if "thumbnail" in n and n.endswith((".png", ".jpg", ".jpeg")):
                target = name
                break
        if target is None:
            return False
        raw = zf.read(target)
    with Image.open(io.BytesIO(raw)) as im:
        im = im.convert("RGB")
        im.thumbnail(size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", size, (245, 246, 248))
        ox = (size[0] - im.width) // 2
        oy = (size[1] - im.height) // 2
        canvas.paste(im, (ox, oy))
        canvas.save(out_png, "PNG", optimize=True)
    return True


@celery_app.task(name="app.tasks.conversion_tasks.generate_file_thumbnail", max_retries=1)
def generate_file_thumbnail(file_id: str) -> dict:
    """Render a per-file thumbnail and store it at derived/thumbs/{file_id}.png.

    Type-aware:
      * .stl/.obj/.fbx mesh   → orthographic Pillow render (no OpenGL)
      * .3mf                  → embedded Metadata/thumbnail.png if present, else mesh render
      * .jpg/.jpeg/.png/.webp → resized to fit the thumbnail box
    Other types (STEP/CAD/video/document/archive) are skipped.
    """
    fid = uuid.UUID(file_id)
    s3 = _s3()
    with SyncSession() as session:
        f = session.get(File, fid)
        if f is None:
            return {"status": "not_found"}

        ext = (f.extension or "").lstrip(".").lower()
        kind: str | None = None
        if f.file_type == FileType.image and ext in ("jpg", "jpeg", "png", "webp", "bmp"):
            kind = "image"
        elif f.file_type == FileType.project and ext == "3mf":
            kind = "3mf"
        elif f.file_type == FileType.mesh and ext in ("stl", "obj", "fbx"):
            kind = "mesh"
        if kind is None:
            return {"status": "unsupported", "file_type": f.file_type.value, "ext": ext}

    # Render outside the DB session — these can be slow.
    key = f"thumbs/{file_id}.png"
    try:
        with tempfile.TemporaryDirectory() as tmp:
            local_src = Path(tmp) / f"src.{ext or 'bin'}"
            local_png = Path(tmp) / "thumb.png"
            s3.download_file(settings.s3_bucket_files, f.storage_key, str(local_src))

            if kind == "image":
                _resize_image_to_thumb(local_src, local_png, THUMB_SIZE)
            elif kind == "3mf":
                ok = _extract_3mf_embedded(local_src, local_png, THUMB_SIZE)
                if not ok:
                    # 3MF without embedded thumbnail → fall back to mesh render via trimesh
                    _render_mesh_thumbnail(local_src, local_png, THUMB_SIZE)
            elif kind == "mesh":
                _render_mesh_thumbnail(local_src, local_png, THUMB_SIZE)

            s3.upload_file(
                str(local_png),
                settings.s3_bucket_derived,
                key,
                ExtraArgs={"ContentType": "image/png"},
            )
        log.info("file.thumb.ok", file_id=file_id, kind=kind, key=key)
        return {"status": "ok", "kind": kind, "key": key}
    except Exception as exc:
        log.error("file.thumb.fail", file_id=file_id, kind=kind, error=str(exc))
        return {"status": "failed", "error": str(exc)}
