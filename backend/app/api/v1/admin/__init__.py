"""Admin-only routers."""
from fastapi import APIRouter

from app.api.v1.admin import invites as invites_router
from app.api.v1.admin import users as users_router

admin_router = APIRouter(prefix="/admin")
admin_router.include_router(invites_router.router, prefix="/invites", tags=["admin:invites"])
admin_router.include_router(users_router.router, prefix="/users", tags=["admin:users"])
