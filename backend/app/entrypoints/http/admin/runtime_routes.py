"""Runtime status endpoints for admin dashboard."""

from fastapi import APIRouter
from app.shared.database.db import get_connection

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get("/health")
async def runtime_health():
    """Database and system health check."""
    try:
        async with get_connection() as conn:
            version = await conn.fetchval("SELECT sqlite_version()")
        return {"status": "ok", "database": "connected", "sqlite_version": version}
    except Exception as e:
        return {"status": "error", "database": "disconnected", "error": str(e)}


@router.get("/stats")
async def runtime_stats():
    """Platform statistics and active bot runtime config."""
    try:
        async with get_connection() as conn:
            bots = await conn.fetchval("SELECT COUNT(*) FROM bots")
            active_bot = await conn.fetchrow("""
                SELECT id, name, description, system_prompt, llm_provider_id, llm_model, 
                       stt_provider_id, tts_provider_id, is_active 
                FROM bots 
                WHERE is_active = 1 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            
            stt_info = None
            tts_info = None
            if active_bot:
                if active_bot["stt_provider_id"]:
                    sp = await conn.fetchrow("""
                        SELECT id, name, provider_type, stt_model 
                        FROM speech_providers WHERE id = ?
                    """, active_bot["stt_provider_id"])
                    if sp:
                        stt_info = dict(sp)
                if active_bot["tts_provider_id"]:
                    sp = await conn.fetchrow("""
                        SELECT id, name, provider_type, tts_model, tts_voice_id 
                        FROM speech_providers WHERE id = ?
                    """, active_bot["tts_provider_id"])
                    if sp:
                        tts_info = dict(sp)

            llm_providers = await conn.fetchval("SELECT COUNT(*) FROM llm_providers")
            speech_providers = await conn.fetchval("SELECT COUNT(*) FROM speech_providers")
            sessions = await conn.fetchval("SELECT COUNT(*) FROM sessions WHERE status = 'active'")

        bot_data = dict(active_bot) if active_bot else None
        if bot_data:
            bot_data["stt_provider"] = stt_info
            bot_data["tts_provider"] = tts_info

        return {
            "bots": bots,
            "active_bot": bot_data,
            "llm_providers": llm_providers,
            "speech_providers": speech_providers,
            "active_sessions": sessions,
        }
    except Exception as e:
        return {"error": str(e)}
