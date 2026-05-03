"""GET /api/v1/categories — full tree with model counts."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import CurrentUser
from app.models import Category, Model
from app.schemas.models import CategoryNode

router = APIRouter()


@router.get("/categories", response_model=list[CategoryNode])
async def categories_tree(
    session: Annotated[AsyncSession, Depends(get_db)],
    _user: CurrentUser,
) -> list[CategoryNode]:
    cats = (await session.execute(select(Category).order_by(Category.path))).scalars().all()

    counts_stmt = (
        select(Model.category_id, func.count(Model.id))
        .group_by(Model.category_id)
    )
    counts_rows = (await session.execute(counts_stmt)).all()
    counts = {cid: cnt for (cid, cnt) in counts_rows if cid is not None}

    by_id: dict = {}
    roots: list[CategoryNode] = []
    for c in cats:
        by_id[c.id] = CategoryNode(
            id=c.id,
            slug=c.slug,
            name=c.name,
            path=c.path,
            sort_order=c.sort_order,
            model_count=counts.get(c.id, 0),
            children=[],
        )

    for c in cats:
        node = by_id[c.id]
        if c.parent_id and c.parent_id in by_id:
            by_id[c.parent_id].children.append(node)
        else:
            roots.append(node)

    return roots
