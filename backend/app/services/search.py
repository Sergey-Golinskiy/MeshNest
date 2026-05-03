"""Meilisearch integration — index models, run search.

Index `models` documents shape:
    {
      "id": "uuid",
      "slug": "flexi_cat",
      "title": "Flexi Cat",
      "original_title": "Flexi_Cat_STL_Pack",
      "category": "animals/cats",
      "tags": ["cat","flexi","articulated"],
      "has_stl": true, "has_3mf": true, "has_step": false,
      "has_images": true, "has_video": false,
      "is_flexi": true, "is_print_in_place": true, "is_multipart": true,
      "is_reviewed": false,
      "imported_at": 1700000000   // unix seconds
    }
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import meilisearch
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.models import Category, Model, Tag


_INDEX_NAME = "models"


def _client() -> meilisearch.Client:
    return meilisearch.Client(
        settings.meilisearch_url,
        settings.meilisearch_master_key.get_secret_value(),
    )


def ensure_index() -> None:
    """Idempotent: создаёт индекс если нет, выставляет searchable/filterable/sortable атрибуты."""
    cl = _client()
    try:
        cl.get_index(_INDEX_NAME)
    except meilisearch.errors.MeilisearchApiError:
        cl.create_index(_INDEX_NAME, {"primaryKey": "id"})

    idx = cl.index(_INDEX_NAME)
    idx.update_settings(
        {
            "searchableAttributes": ["title", "original_title", "tags", "category"],
            "filterableAttributes": [
                "category",
                "tags",
                "has_stl",
                "has_3mf",
                "has_step",
                "has_images",
                "has_video",
                "is_flexi",
                "is_print_in_place",
                "is_multipart",
                "is_reviewed",
            ],
            "sortableAttributes": ["imported_at", "title"],
            "displayedAttributes": ["*"],
        }
    )


def _to_doc(model: Model) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "slug": model.slug,
        "title": model.title,
        "original_title": model.original_title or "",
        "category": model.category.path if model.category else "uncategorized",
        "tags": [t.slug for t in model.tags],
        "has_stl": model.has_stl,
        "has_3mf": model.has_3mf,
        "has_step": model.has_step,
        "has_images": model.has_images,
        "has_video": model.has_video,
        "is_flexi": model.is_flexi,
        "is_print_in_place": model.is_print_in_place,
        "is_multipart": model.is_multipart,
        "is_reviewed": model.is_reviewed,
        "imported_at": int(model.imported_at.timestamp())
        if model.imported_at
        else int(model.created_at.timestamp()),
    }


def index_models(models: list[Model]) -> dict[str, Any]:
    if not models:
        return {"indexed": 0}
    docs = [_to_doc(m) for m in models]
    cl = _client()
    idx = cl.index(_INDEX_NAME)
    task = idx.add_documents(docs, primary_key="id")
    return {"indexed": len(docs), "task_uid": getattr(task, "task_uid", None)}


def index_one(session: Session, model_id: UUID) -> None:
    m = session.get(Model, model_id)
    if m is None:
        return
    # Hydrate relationships (tags, category) for sync session
    session.refresh(m, attribute_names=["tags", "category"])
    _client().index(_INDEX_NAME).add_documents([_to_doc(m)], primary_key="id")


def remove_one(model_id: UUID) -> None:
    _client().index(_INDEX_NAME).delete_document(str(model_id))


def reindex_all(session: Session, batch_size: int = 500) -> dict[str, int]:
    """Полный пересбор индекса — для periodic maintenance task."""
    ensure_index()
    cl = _client()
    idx = cl.index(_INDEX_NAME)
    idx.delete_all_documents()  # сбрасываем

    total = 0
    offset = 0
    from sqlalchemy import select

    while True:
        rows = (
            session.execute(
                select(Model)
                .options(selectinload(Model.tags), selectinload(Model.category))
                .order_by(Model.created_at)
                .offset(offset)
                .limit(batch_size)
            )
            .scalars()
            .all()
        )
        if not rows:
            break
        docs = [_to_doc(m) for m in rows]
        idx.add_documents(docs, primary_key="id")
        total += len(docs)
        offset += batch_size
    return {"indexed": total}


def search(
    q: str,
    *,
    filters: list[str] | None = None,
    limit: int = 24,
    offset: int = 0,
    sort: list[str] | None = None,
) -> dict[str, Any]:
    cl = _client()
    idx = cl.index(_INDEX_NAME)
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if filters:
        params["filter"] = filters
    if sort:
        params["sort"] = sort
    return idx.search(q or "", params)
