"""Admin: list / create / revoke invites."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.invites import create_invite
from app.config import settings
from app.db import get_db
from app.deps import require_admin
from app.models import Invite, User
from app.schemas.auth import InviteCreateRequest, InviteOut

router = APIRouter()


def _to_out(invite: Invite) -> InviteOut:
    return InviteOut(
        id=invite.id,
        token=invite.token,
        role=invite.role,
        email_hint=invite.email_hint,
        expires_at=invite.expires_at,
        used_at=invite.used_at,
        created_at=invite.created_at,
        invite_url=f"{settings.frontend_url.rstrip('/')}/invite/{invite.token}",
    )


@router.get("", response_model=list[InviteOut])
async def list_invites(
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
    include_used: bool = False,
) -> list[InviteOut]:
    stmt = select(Invite).order_by(desc(Invite.created_at))
    if not include_used:
        stmt = stmt.where(Invite.used_at.is_(None))
    result = await session.execute(stmt)
    return [_to_out(i) for i in result.scalars().all()]


@router.post("", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
async def create_invite_endpoint(
    body: InviteCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> InviteOut:
    invite = await create_invite(
        session,
        role=body.role,
        created_by=admin,
        expires_in_days=body.expires_in_days,
        email_hint=body.email_hint,
    )
    out = _to_out(invite)

    # Если SMTP настроен И есть email_hint — отправляем письмо
    if body.email_hint:
        from app.services.email import send_invite_email

        await send_invite_email(
            to=body.email_hint,
            invite_url=out.invite_url,
            role=invite.role.value,
            expires_at=invite.expires_at.strftime("%Y-%m-%d %H:%M UTC"),
        )
    return out


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_invite(
    invite_id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> Response:
    invite = await session.get(Invite, invite_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    if invite.used_at is not None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot delete used invite (history is preserved)",
        )
    await session.delete(invite)
    await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
