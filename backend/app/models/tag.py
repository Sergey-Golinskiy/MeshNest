from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models._types import TagType, created_at_ts, uuid_pk

if TYPE_CHECKING:
    from app.models.model import Model


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    type: Mapped[TagType] = mapped_column(
        Enum(TagType, name="tag_type"),
        nullable=False,
        default=TagType.topic,
    )

    created_at: Mapped[datetime] = created_at_ts()

    models: Mapped[list[Model]] = relationship(
        secondary="model_tags", back_populates="tags"
    )


class ModelTag(Base):
    __tablename__ = "model_tags"

    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("models.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
