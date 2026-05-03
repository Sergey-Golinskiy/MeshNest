"""Password hashing via bcrypt (direct, not passlib).

passlib >=1.7.4 is unmaintained and incompatible with bcrypt >=4.1; we
use the bcrypt library directly. bcrypt itself silently truncates
secrets at 72 bytes, but to keep behaviour explicit we pre-encode and
clamp here.
"""
from __future__ import annotations

import bcrypt

from app.config import settings


def _encode(plain: str) -> bytes:
    # bcrypt operates on raw bytes; max length is 72.
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(_encode(plain), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(plain), hashed.encode("utf-8"))
    except ValueError:
        return False
