from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._types import UserRole, created_at_ts, uuid_pk

if TYPE_CHECKING:
    from app.models.user import User


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = uuid_pk()
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", create_type=False),
        nullable=False,
        default=UserRole.viewer,
    )
    email_hint: Mapped[str | None] = mapped_column(String(320))  # для удобства, не строгое поле

    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    used_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = created_at_ts()

    created_by_user: Mapped[User | None] = relationship(
        foreign_keys=[created_by], back_populates="invites_created"
    )
    used_by_user: Mapped[User | None] = relationship(foreign_keys=[used_by])
