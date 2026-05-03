"""Admin: list users + change role / disable."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import require_admin
from app.models import User
from app.models._types import UserRole
from app.schemas.auth import UserOut

router = APIRouter()


class UserPatch(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


@router.get("", response_model=list[UserOut])
async def list_users(
    session: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> list[UserOut]:
    result = await session.execute(select(User).order_by(desc(User.created_at)))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.patch("/{user_id}", response_model=UserOut)
async def patch_user(
    user_id: uuid.UUID,
    body: UserPatch,
    session: Annotated[AsyncSession, Depends(get_db)],
    admin: Annotated[User, Depends(require_admin)],
) -> UserOut:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and body.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot disable yourself")
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    await session.flush()
    return UserOut.model_validate(user)
