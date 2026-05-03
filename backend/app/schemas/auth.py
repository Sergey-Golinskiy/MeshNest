"""Auth-related request / response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models._types import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str


class InviteRedeemRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str | None = Field(default=None, max_length=120)


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    user: UserOut


class AccessOnly(BaseModel):
    access_token: str
    access_expires_at: datetime


class InviteInfo(BaseModel):
    token: str
    role: UserRole
    expires_at: datetime
    email_hint: str | None = None
    valid: bool


class InviteCreateRequest(BaseModel):
    role: UserRole = UserRole.viewer
    expires_in_days: int = Field(default=7, ge=1, le=90)
    email_hint: str | None = Field(default=None, max_length=320)


class InviteOut(BaseModel):
    id: uuid.UUID
    token: str
    role: UserRole
    email_hint: str | None
    expires_at: datetime
    used_at: datetime | None
    created_at: datetime
    invite_url: str

    class Config:
        from_attributes = True
