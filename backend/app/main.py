"""FastAPI application entrypoint."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app import __version__
from app.config import settings
from app.core.ratelimit import limiter


def _configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(message)s",
    )
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level)
        ),
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
            if settings.is_production
            else structlog.dev.ConsoleRenderer(),
        ],
        cache_logger_on_first_use=True,
    )


_configure_logging()
log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", version=__version__, env=settings.environment)

    # Ensure MinIO buckets exist (idempotent)
    try:
        from app.services.storage import get_storage

        storage = get_storage()
        for b in (
            settings.s3_bucket_files,
            settings.s3_bucket_derived,
            settings.s3_bucket_imports,
        ):
            await storage.ensure_bucket(b)
        log.info("startup.buckets_ok")
    except Exception as exc:
        log.warning("startup.buckets_failed", error=str(exc))

    # Ensure Meilisearch index (idempotent, sync — но быстрый)
    try:
        from app.services import search as search_svc

        search_svc.ensure_index()
        log.info("startup.meili_ok")
    except Exception as exc:
        log.warning("startup.meili_failed", error=str(exc))

    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="MeshNest API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/healthz", tags=["meta"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/readyz", tags=["meta"])
    async def readyz(request: Request) -> JSONResponse:
        from app.db import healthcheck as db_healthcheck

        try:
            db = await db_healthcheck()
        except Exception as exc:
            log.error("readyz.db_failed", error=str(exc))
            return JSONResponse({"status": "down", "db": "fail"}, status_code=503)
        return JSONResponse({"status": "ok", **db})

    from app.api.v1 import api_v1

    app.include_router(api_v1)

    return app


app = create_app()
