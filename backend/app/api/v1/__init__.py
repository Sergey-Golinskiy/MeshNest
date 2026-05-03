"""API v1 routers."""
from fastapi import APIRouter

from app.api.v1 import (
    auth,
    categories,
    files,
    import_jobs,
    import_package,
    me,
    models,
    search,
    tags,
    uploads,
)
from app.api.v1.admin import admin_router

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth.router, prefix="/auth", tags=["auth"])
api_v1.include_router(me.router, tags=["me"])
api_v1.include_router(models.router, tags=["models"])
api_v1.include_router(files.router, tags=["files"])
api_v1.include_router(categories.router, tags=["categories"])
api_v1.include_router(tags.router, tags=["tags"])
api_v1.include_router(search.router, tags=["search"])
api_v1.include_router(uploads.router, tags=["uploads"])
api_v1.include_router(import_package.router, tags=["import-package"])
api_v1.include_router(import_jobs.router, tags=["import-jobs"])
api_v1.include_router(admin_router)
