"""
Admin REST API routes.

All provider credentials, bot configuration, and platform management
are handled through these endpoints. No .env-driven config remains.
"""

from fastapi import APIRouter

from app.entrypoints.http.admin.bot_routes import router as bot_router
from app.entrypoints.http.admin.llm_provider_routes import router as llm_router
from app.entrypoints.http.admin.speech_provider_routes import router as speech_router
from app.entrypoints.http.admin.runtime_routes import router as runtime_router

admin_router = APIRouter(prefix="/admin/api", tags=["admin"])

admin_router.include_router(bot_router)
admin_router.include_router(llm_router)
admin_router.include_router(speech_router)
admin_router.include_router(runtime_router)
