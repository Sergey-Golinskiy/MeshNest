"""FastAPI dependencies — auth, db session, role guards."""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import TokenError, decode_token
from app.db import get_db
from app.models import User
from app.models._types import UserRole

bearer = HTTPBearer(auto_error=True)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    session: DbSession,
) -> User:
    try:
        payload = decode_token(creds.credentials, expected_type="access")
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await session.get(User, payload.sub)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed: UserRole):
    async def _check(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {[r.value for r in allowed]}",
            )
        return user

    return _check


require_admin = require_role(UserRole.admin)
require_contributor = require_role(UserRole.admin, UserRole.contributor)
