"""Invite token generation + redeem helpers."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Invite, User
from app.models._types import UserRole


def _now() -> datetime:
    return datetime.now(timezone.utc)


def generate_token() -> str:
    """URL-safe random token, 256 bits of entropy."""
    return secrets.token_urlsafe(32)


async def create_invite(
    session: AsyncSession,
    *,
    role: UserRole,
    created_by: User,
    expires_in_days: int | None = None,
    email_hint: str | None = None,
) -> Invite:
    ttl = expires_in_days or settings.invite_default_ttl_days
    invite = Invite(
        token=generate_token(),
        role=role,
        email_hint=email_hint,
        created_by=created_by.id,
        expires_at=_now() + timedelta(days=ttl),
    )
    session.add(invite)
    await session.flush()
    return invite


async def get_valid_invite(session: AsyncSession, token: str) -> Invite | None:
    result = await session.execute(select(Invite).where(Invite.token == token))
    invite = result.scalar_one_or_none()
    if not invite:
        return None
    if invite.used_at is not None:
        return None
    if invite.expires_at <= _now():
        return None
    return invite


async def consume_invite(session: AsyncSession, invite: Invite, user: User) -> None:
    invite.used_at = _now()
    invite.used_by = user.id
    await session.flush()
