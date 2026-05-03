"""Auth endpoints: /login, /refresh, /invite/{token}/info, /invite/{token}/redeem."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.invites import consume_invite, get_valid_invite
from app.auth.jwt import (
    TokenError,
    decode_token,
    hash_refresh_for_db,
    issue_access_token,
    issue_refresh_token,
)
from app.auth.passwords import hash_password, verify_password
from app.config import settings
from app.core.ratelimit import limiter
from app.db import get_db
from app.models import RefreshToken, User
from app.schemas.auth import (
    AccessOnly,
    InviteInfo,
    InviteRedeemRequest,
    LoginRequest,
    RefreshRequest,
    TokenPair,
    UserOut,
)

router = APIRouter()
log = structlog.get_logger()


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _issue_pair(
    session: AsyncSession,
    user: User,
    request: Request,
) -> TokenPair:
    access, access_exp = issue_access_token(user.id, user.role)
    raw_refresh, refresh_hash, refresh_exp = issue_refresh_token(user.id, user.role)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_exp,
        user_agent=request.headers.get("user-agent", "")[:255] or None,
        ip_address=(request.client.host if request.client else None),
    )
    session.add(rt)
    user.last_login_at = _now()
    await session.flush()
    return TokenPair(
        access_token=access,
        refresh_token=raw_refresh,
        access_expires_at=access_exp,
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=TokenPair)
@limiter.limit(settings.rate_limit_login)
async def login(
    request: Request,
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        log.info("login.failed", email=body.email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User is disabled")
    log.info("login.success", user_id=str(user.id))
    return await _issue_pair(session, user, request)


@router.post("/refresh", response_model=AccessOnly)
async def refresh(
    body: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AccessOnly:
    try:
        payload = decode_token(body.refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    h = hash_refresh_for_db(body.refresh_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == h)
    )
    rt = result.scalar_one_or_none()
    if rt is None or rt.revoked_at is not None or rt.expires_at <= _now():
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked or expired")

    user = await session.get(User, payload.sub)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")

    access, access_exp = issue_access_token(user.id, user.role)
    return AccessOnly(access_token=access, access_expires_at=access_exp)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    h = hash_refresh_for_db(body.refresh_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == h)
    )
    rt = result.scalar_one_or_none()
    if rt and rt.revoked_at is None:
        rt.revoked_at = _now()
        await session.flush()


@router.get("/invite/{token}/info", response_model=InviteInfo)
@limiter.limit(settings.rate_limit_invite_redeem)
async def invite_info(
    request: Request,
    token: str,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> InviteInfo:
    invite = await get_valid_invite(session, token)
    if invite is None:
        # Не утечь existence — возвращаем валидный schema c valid=False
        return InviteInfo(
            token=token,
            role="viewer",  # type: ignore[arg-type]
            expires_at=_now(),
            valid=False,
        )
    return InviteInfo(
        token=invite.token,
        role=invite.role,
        expires_at=invite.expires_at,
        email_hint=invite.email_hint,
        valid=True,
    )


@router.post("/invite/{token}/redeem", response_model=TokenPair)
@limiter.limit(settings.rate_limit_invite_redeem)
async def invite_redeem(
    request: Request,
    token: str,
    body: InviteRedeemRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPair:
    invite = await get_valid_invite(session, token)
    if invite is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired invite")

    # Проверка что email не занят
    existing = await session.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=invite.role,
        display_name=body.display_name,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await consume_invite(session, invite, user)

    log.info("invite.redeemed", user_id=str(user.id), invite_id=str(invite.id))
    return await _issue_pair(session, user, request)
