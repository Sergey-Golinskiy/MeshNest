"""Local chunk-buffer for chunked uploads.

Хранит chunks в `/var/lib/meshnest/uploads/{upload_id}/chunk-{n:04d}.bin`
+ `meta.json` с прогрессом.

После complete — склеивает chunks в один файл, заливает в MinIO bucket `meshnest-imports`,
чистит локальный буфер. Возвращает storage_key.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.services.storage import get_storage


_BUFFER_ROOT = Path(os.getenv("MESHNEST_UPLOAD_BUFFER", "/var/lib/meshnest/uploads"))


@dataclass
class UploadMeta:
    upload_id: str
    filename: str
    total_size: int
    chunk_size: int
    total_chunks: int
    expected_sha256: str | None
    received_chunks: list[int] = field(default_factory=list)
    created_at: str = ""
    finalized_at: str | None = None
    storage_key: str | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_json(cls, raw: str) -> "UploadMeta":
        data = json.loads(raw)
        return cls(**data)


def _dir(upload_id: str) -> Path:
    return _BUFFER_ROOT / upload_id


def _meta_path(upload_id: str) -> Path:
    return _dir(upload_id) / "meta.json"


def _chunk_path(upload_id: str, n: int) -> Path:
    return _dir(upload_id) / f"chunk-{n:04d}.bin"


def init_upload(filename: str, total_size: int, expected_sha256: str | None) -> UploadMeta:
    upload_id = uuid.uuid4().hex
    chunk_size = settings.upload_chunk_max_bytes
    total_chunks = (total_size + chunk_size - 1) // chunk_size
    if total_size > settings.upload_max_total_bytes:
        raise ValueError(f"File too large: max {settings.upload_max_total_bytes} bytes")

    meta = UploadMeta(
        upload_id=upload_id,
        filename=filename,
        total_size=total_size,
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        expected_sha256=expected_sha256,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _dir(upload_id).mkdir(parents=True, exist_ok=True)
    _meta_path(upload_id).write_text(meta.to_json(), encoding="utf-8")
    return meta


def load_meta(upload_id: str) -> UploadMeta | None:
    p = _meta_path(upload_id)
    if not p.exists():
        return None
    return UploadMeta.from_json(p.read_text(encoding="utf-8"))


def save_meta(meta: UploadMeta) -> None:
    _meta_path(meta.upload_id).write_text(meta.to_json(), encoding="utf-8")


def write_chunk(upload_id: str, chunk_index: int, data: bytes) -> UploadMeta:
    meta = load_meta(upload_id)
    if meta is None:
        raise FileNotFoundError(f"Upload {upload_id} not found")
    if meta.finalized_at:
        raise RuntimeError("Upload already finalized")
    if chunk_index < 0 or chunk_index >= meta.total_chunks:
        raise ValueError(f"Invalid chunk_index {chunk_index} (total={meta.total_chunks})")
    if len(data) > meta.chunk_size:
        raise ValueError(f"Chunk too large: {len(data)} > {meta.chunk_size}")

    _chunk_path(upload_id, chunk_index).write_bytes(data)
    if chunk_index not in meta.received_chunks:
        meta.received_chunks.append(chunk_index)
        meta.received_chunks.sort()
        save_meta(meta)
    return meta


async def complete_upload(upload_id: str) -> UploadMeta:
    meta = load_meta(upload_id)
    if meta is None:
        raise FileNotFoundError(f"Upload {upload_id} not found")
    if meta.finalized_at:
        return meta

    expected = set(range(meta.total_chunks))
    received = set(meta.received_chunks)
    missing = sorted(expected - received)
    if missing:
        raise RuntimeError(f"Missing chunks: {missing[:10]}...")

    # Stream-склеиваем в один файл и стримим в S3
    storage = get_storage()
    await storage.ensure_bucket(settings.s3_bucket_imports)

    final_local = _dir(upload_id) / "_final.bin"
    sha = hashlib.sha256()
    total_written = 0
    with final_local.open("wb") as out:
        for n in range(meta.total_chunks):
            chunk = _chunk_path(upload_id, n).read_bytes()
            out.write(chunk)
            sha.update(chunk)
            total_written += len(chunk)
    if total_written != meta.total_size:
        raise RuntimeError(
            f"Size mismatch: assembled={total_written} expected={meta.total_size}"
        )
    actual_sha = sha.hexdigest()
    if meta.expected_sha256 and meta.expected_sha256.lower() != actual_sha:
        raise RuntimeError(
            f"SHA mismatch: expected={meta.expected_sha256} actual={actual_sha}"
        )

    storage_key = f"uploads/{upload_id}/{meta.filename}"
    with final_local.open("rb") as f:
        await storage.put_stream(
            settings.s3_bucket_imports,
            storage_key,
            f,
            size=meta.total_size,
            content_type="application/zip",
        )

    meta.finalized_at = datetime.now(timezone.utc).isoformat()
    meta.storage_key = storage_key
    save_meta(meta)

    # Очищаем chunks локально (meta + storage_key оставляем для истории)
    for n in range(meta.total_chunks):
        _chunk_path(upload_id, n).unlink(missing_ok=True)
    final_local.unlink(missing_ok=True)
    return meta


def cleanup(upload_id: str) -> None:
    d = _dir(upload_id)
    if d.exists():
        for f in d.iterdir():
            f.unlink(missing_ok=True)
        d.rmdir()
