"""GET /me — current user info."""
from __future__ import annotations

from fastapi import APIRouter

from app.deps import CurrentUser
from app.schemas.auth import UserOut

router = APIRouter()


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)
