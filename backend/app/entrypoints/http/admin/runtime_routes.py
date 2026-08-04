"""Runtime status endpoints for admin dashboard."""

from fastapi import APIRouter
from app.shared.database.db import get_connection

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/health")
async def runtime_health():
    """Database and system health check."""
    try:
        async with get_connection() as conn:
            version = await conn.fetchval("SELECT version()")
        return {"status": "ok", "database": "connected", "pg_version": version}
    except Exception as e:
        return {"status": "error", "database": "disconnected", "error": str(e)}


@router.get("/stats")
async def runtime_stats():
    """Platform statistics."""
    try:
        async with get_connection() as conn:
            bots = await conn.fetchval("SELECT COUNT(*) FROM bots")
            active_bot = await conn.fetchrow("SELECT id, name FROM bots WHERE is_active = TRUE")
            llm_providers = await conn.fetchval("SELECT COUNT(*) FROM llm_providers")
            speech_providers = await conn.fetchval("SELECT COUNT(*) FROM speech_providers")
            sessions = await conn.fetchval("SELECT COUNT(*) FROM sessions WHERE status = 'active'")

        return {
            "bots": bots,
            "active_bot": dict(active_bot) if active_bot else None,
            "llm_providers": llm_providers,
            "speech_providers": speech_providers,
            "active_sessions": sessions,
        }
    except Exception as e:
        return {"error": str(e)}
