"""Object storage abstraction.

`Storage` — single interface для load/store/presign файлов.
Реализации:
  - `S3Storage`  — boto3/aioboto3 (работает с MinIO и AWS S3 / Cloudflare R2)
  - `LocalStorage` — для dev/tests, кладёт файлы под `./.local-storage/{bucket}/{key}`

Выбор реализации делается через `get_storage()` (env-based).
"""
from __future__ import annotations

import abc
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

import aioboto3
from botocore.config import Config as BotoConfig

from app.config import settings


@dataclass(frozen=True)
class StorageObject:
    bucket: str
    key: str
    size: int
    etag: str | None = None
    content_type: str | None = None


class Storage(abc.ABC):
    """Abstract storage interface."""

    @abc.abstractmethod
    async def put_bytes(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str | None = None,
    ) -> StorageObject: ...

    @abc.abstractmethod
    async def put_stream(
        self,
        bucket: str,
        key: str,
        fileobj: BinaryIO,
        size: int,
        content_type: str | None = None,
    ) -> StorageObject: ...

    @abc.abstractmethod
    async def get_bytes(self, bucket: str, key: str) -> bytes: ...

    @abc.abstractmethod
    async def stream_get(self, bucket: str, key: str) -> AsyncIterator[bytes]: ...

    @abc.abstractmethod
    async def stat(self, bucket: str, key: str) -> StorageObject | None: ...

    @abc.abstractmethod
    async def delete(self, bucket: str, key: str) -> None: ...

    @abc.abstractmethod
    async def presign_get(self, bucket: str, key: str, ttl_sec: int) -> str: ...

    @abc.abstractmethod
    async def presign_put(self, bucket: str, key: str, ttl_sec: int) -> str: ...

    @abc.abstractmethod
    async def ensure_bucket(self, bucket: str) -> None: ...


class S3Storage(Storage):
    """Boto3 / aioboto3 backend — work с MinIO и любым S3-API."""

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        region: str,
        use_ssl: bool,
    ) -> None:
        self._session = aioboto3.Session()
        self._endpoint = endpoint_url
        self._access_key = access_key
        self._secret_key = secret_key
        self._region = region
        self._use_ssl = use_ssl
        self._cfg = BotoConfig(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        )

    def _client(self):
        return self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=self._region,
            use_ssl=self._use_ssl,
            config=self._cfg,
        )

    async def ensure_bucket(self, bucket: str) -> None:
        async with self._client() as s3:
            try:
                await s3.head_bucket(Bucket=bucket)
            except s3.exceptions.ClientError:
                await s3.create_bucket(Bucket=bucket)

    async def put_bytes(
        self, bucket: str, key: str, data: bytes, content_type: str | None = None
    ) -> StorageObject:
        async with self._client() as s3:
            kwargs = {"Bucket": bucket, "Key": key, "Body": data}
            if content_type:
                kwargs["ContentType"] = content_type
            res = await s3.put_object(**kwargs)
        return StorageObject(
            bucket=bucket, key=key, size=len(data),
            etag=res.get("ETag"), content_type=content_type,
        )

    async def put_stream(
        self,
        bucket: str,
        key: str,
        fileobj: BinaryIO,
        size: int,
        content_type: str | None = None,
    ) -> StorageObject:
        async with self._client() as s3:
            kwargs = {"Bucket": bucket, "Key": key, "Body": fileobj}
            if content_type:
                kwargs["ContentType"] = content_type
            res = await s3.put_object(**kwargs)
        return StorageObject(
            bucket=bucket, key=key, size=size,
            etag=res.get("ETag"), content_type=content_type,
        )

    async def get_bytes(self, bucket: str, key: str) -> bytes:
        async with self._client() as s3:
            res = await s3.get_object(Bucket=bucket, Key=key)
            async with res["Body"] as stream:
                return await stream.read()

    async def stream_get(self, bucket: str, key: str) -> AsyncIterator[bytes]:
        async with self._client() as s3:
            res = await s3.get_object(Bucket=bucket, Key=key)
            async with res["Body"] as stream:
                async for chunk in stream.iter_chunks(chunk_size=1 * 1024 * 1024):
                    yield chunk

    async def stat(self, bucket: str, key: str) -> StorageObject | None:
        async with self._client() as s3:
            try:
                head = await s3.head_object(Bucket=bucket, Key=key)
            except s3.exceptions.ClientError:
                return None
        return StorageObject(
            bucket=bucket,
            key=key,
            size=int(head.get("ContentLength", 0)),
            etag=head.get("ETag"),
            content_type=head.get("ContentType"),
        )

    async def delete(self, bucket: str, key: str) -> None:
        async with self._client() as s3:
            await s3.delete_object(Bucket=bucket, Key=key)

    async def presign_get(self, bucket: str, key: str, ttl_sec: int) -> str:
        async with self._client() as s3:
            return await s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=ttl_sec,
            )

    async def presign_put(self, bucket: str, key: str, ttl_sec: int) -> str:
        async with self._client() as s3:
            return await s3.generate_presigned_url(
                "put_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=ttl_sec,
            )


class LocalStorage(Storage):
    """Dev-only backend — кладёт файлы на FS, presign возвращает file:// URL."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, bucket: str, key: str) -> Path:
        p = self._root / bucket / key
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    async def ensure_bucket(self, bucket: str) -> None:
        (self._root / bucket).mkdir(parents=True, exist_ok=True)

    async def put_bytes(
        self, bucket: str, key: str, data: bytes, content_type: str | None = None
    ) -> StorageObject:
        p = self._path(bucket, key)
        p.write_bytes(data)
        return StorageObject(bucket=bucket, key=key, size=len(data), content_type=content_type)

    async def put_stream(
        self,
        bucket: str,
        key: str,
        fileobj: BinaryIO,
        size: int,
        content_type: str | None = None,
    ) -> StorageObject:
        p = self._path(bucket, key)
        with p.open("wb") as f:
            while True:
                chunk = fileobj.read(1 * 1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        return StorageObject(bucket=bucket, key=key, size=size, content_type=content_type)

    async def get_bytes(self, bucket: str, key: str) -> bytes:
        return self._path(bucket, key).read_bytes()

    async def stream_get(self, bucket: str, key: str) -> AsyncIterator[bytes]:
        path = self._path(bucket, key)
        with path.open("rb") as f:
            while True:
                chunk = f.read(1 * 1024 * 1024)
                if not chunk:
                    return
                yield chunk

    async def stat(self, bucket: str, key: str) -> StorageObject | None:
        p = self._path(bucket, key)
        if not p.exists():
            return None
        return StorageObject(bucket=bucket, key=key, size=p.stat().st_size)

    async def delete(self, bucket: str, key: str) -> None:
        p = self._path(bucket, key)
        if p.exists():
            p.unlink()

    async def presign_get(self, bucket: str, key: str, ttl_sec: int) -> str:
        return f"file://{self._path(bucket, key)}"

    async def presign_put(self, bucket: str, key: str, ttl_sec: int) -> str:
        return f"file://{self._path(bucket, key)}"


_storage_singleton: Storage | None = None


def get_storage() -> Storage:
    global _storage_singleton
    if _storage_singleton is not None:
        return _storage_singleton

    if os.getenv("MESHNEST_STORAGE_DRIVER") == "local":
        _storage_singleton = LocalStorage(
            root=Path(os.getenv("MESHNEST_LOCAL_STORAGE_ROOT", "./.local-storage"))
        )
    else:
        _storage_singleton = S3Storage(
            endpoint_url=settings.s3_endpoint_url,
            access_key=settings.s3_access_key.get_secret_value(),
            secret_key=settings.s3_secret_key.get_secret_value(),
            region=settings.s3_region,
            use_ssl=settings.s3_use_ssl,
        )
    return _storage_singleton
