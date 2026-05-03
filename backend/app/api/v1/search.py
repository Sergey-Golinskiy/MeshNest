"""POST /api/v1/search — Meilisearch proxy."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.deps import CurrentUser
from app.services import search as search_svc

router = APIRouter()


class SearchFilters(BaseModel):
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    has_stl: bool | None = None
    has_3mf: bool | None = None
    has_step: bool | None = None
    is_flexi: bool | None = None
    is_print_in_place: bool | None = None
    is_reviewed: bool | None = None


class SearchRequest(BaseModel):
    q: str = ""
    filters: SearchFilters = Field(default_factory=SearchFilters)
    limit: int = Field(24, ge=1, le=100)
    offset: int = Field(0, ge=0)
    sort: list[str] | None = None


def _build_filters(f: SearchFilters) -> list[str]:
    out: list[str] = []
    if f.category:
        out.append(f'category = "{f.category}"')
    for t in f.tags:
        out.append(f'tags = "{t}"')
    flag_map = {
        "has_stl": f.has_stl,
        "has_3mf": f.has_3mf,
        "has_step": f.has_step,
        "is_flexi": f.is_flexi,
        "is_print_in_place": f.is_print_in_place,
        "is_reviewed": f.is_reviewed,
    }
    for key, val in flag_map.items():
        if val is not None:
            out.append(f"{key} = {'true' if val else 'false'}")
    return out


@router.post("/search")
async def search_models(body: SearchRequest, _user: CurrentUser) -> dict[str, Any]:
    try:
        return search_svc.search(
            body.q,
            filters=_build_filters(body.filters),
            limit=body.limit,
            offset=body.offset,
            sort=body.sort,
        )
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Search service unavailable: {exc}",
        ) from exc
