from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._types import created_at_ts, updated_at_ts, uuid_pk

if TYPE_CHECKING:
    from app.models.model import Model


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = uuid_pk()
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(String(400), index=True, nullable=False)  # e.g. "animals/cats"
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = created_at_ts()
    updated_at: Mapped[datetime] = updated_at_ts()

    parent: Mapped[Category | None] = relationship(
        "Category", remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list[Category]] = relationship("Category", back_populates="parent")
    models: Mapped[list[Model]] = relationship(back_populates="category")
