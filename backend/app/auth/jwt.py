"""JWT issue / decode for access + refresh tokens."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from jwt import InvalidTokenError

from app.config import settings
from app.models._types import UserRole


class TokenError(Exception):
    """Raised on any JWT validation failure."""


@dataclass(frozen=True)
class TokenPayload:
    sub: uuid.UUID
    role: UserRole
    type: Literal["access", "refresh"]
    jti: str
    exp: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict) -> str:
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def issue_access_token(user_id: uuid.UUID, role: UserRole) -> tuple[str, datetime]:
    expires = _now() + timedelta(minutes=settings.jwt_access_ttl_min)
    jti = secrets.token_urlsafe(12)
    token = _encode(
        {
            "sub": str(user_id),
            "role": role.value,
            "type": "access",
            "jti": jti,
            "iat": int(_now().timestamp()),
            "exp": int(expires.timestamp()),
        }
    )
    return token, expires


def issue_refresh_token(user_id: uuid.UUID, role: UserRole) -> tuple[str, str, datetime]:
    """Возвращает (raw_token, sha256_hash_for_db, expires_at)."""
    expires = _now() + timedelta(days=settings.jwt_refresh_ttl_days)
    jti = secrets.token_urlsafe(16)
    raw = _encode(
        {
            "sub": str(user_id),
            "role": role.value,
            "type": "refresh",
            "jti": jti,
            "iat": int(_now().timestamp()),
            "exp": int(expires.timestamp()),
        }
    )
    h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return raw, h, expires


def decode_token(raw: str, expected_type: Literal["access", "refresh"]) -> TokenPayload:
    try:
        payload = jwt.decode(
            raw,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise TokenError(f"Invalid token: {exc}") from exc

    if payload.get("type") != expected_type:
        raise TokenError(f"Wrong token type (expected {expected_type})")

    try:
        return TokenPayload(
            sub=uuid.UUID(payload["sub"]),
            role=UserRole(payload["role"]),
            type=payload["type"],
            jti=payload["jti"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    except (KeyError, ValueError) as exc:
        raise TokenError(f"Malformed payload: {exc}") from exc


def hash_refresh_for_db(raw_refresh: str) -> str:
    return hashlib.sha256(raw_refresh.encode("utf-8")).hexdigest()
