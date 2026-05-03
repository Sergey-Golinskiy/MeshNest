"""GET /api/v1/tags — list of tags with counts."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import CurrentUser
from app.models import ModelTag, Tag
from app.schemas.models import TagOut

router = APIRouter()


@router.get("/tags", response_model=list[TagOut])
async def list_tags(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
) -> list[TagOut]:
    counts_stmt = (
        select(ModelTag.tag_id, func.count(ModelTag.model_id))
        .group_by(ModelTag.tag_id)
    )
    counts = {tid: cnt for (tid, cnt) in (await session.execute(counts_stmt)).all()}

    tags = (await session.execute(select(Tag).order_by(Tag.slug))).scalars().all()
    return [
        TagOut(
            id=t.id,
            slug=t.slug,
            name=t.name,
            type=t.type,
            model_count=counts.get(t.id, 0),
        )
        for t in tags
    ]
