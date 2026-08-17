"""
Public bot routes — accessed by end users via deploy links.

These endpoints are unauthenticated. They allow users to:
1. Fetch a deployed bot's public info by slug
2. Mint a LiveKit token for a specific deployed bot
"""

import uuid
import logging
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.bot.infrastructure.persistence.postgres_bot_repository import (
    PostgresBotRepository,
)
from app.modules.voice.infrastructure.persistence.realtime_config_repository import (
    RealtimeConfigRepository,
)
from app.modules.session.infrastructure.persistence.postgres_session_repository import (
    PostgresSessionRepository,
)
from app.modules.provider.infrastructure.persistence.postgres_speech_provider_repository import (
    PostgresSpeechProviderRepository,
)
from app.modules.provider.infrastructure.persistence.postgres_llm_provider_repository import (
    PostgresLLMProviderRepository,
)
from app.shared.security.envelope_encryption import load_and_decrypt
from app.shared.schemas import TokenResponse, PublicBotResponse

logger = logging.getLogger("public_bot_routes")
router = APIRouter(prefix="/api/bot", tags=["public-bot"])

_bot_repo = PostgresBotRepository()
_config_repo = RealtimeConfigRepository()
_session_repo = PostgresSessionRepository()
_speech_repo = PostgresSpeechProviderRepository()
_llm_repo = PostgresLLMProviderRepository()


async def _decrypt_value(encrypted: dict) -> str:
    blob = encrypted["blob"]
    kv = encrypted["key_version"]
    result = await load_and_decrypt(blob, kv)
    return result["value"]


@router.get("/{slug}", response_model=PublicBotResponse)
async def get_bot_by_slug(slug: str):
    """Get a deployed bot's public info by slug."""
    bot = await _bot_repo.get_by_slug(slug)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {
        "id": bot["id"],
        "name": bot.get("name", ""),
        "description": bot.get("description", ""),
        "is_deployed": bot.get("is_deployed", False),
    }


class BotSlugTokenRequest(BaseModel):
    conversation_type: str = "bot_session"


@router.post("/{slug}/token", response_model=TokenResponse)
async def mint_token_for_bot(slug: str, req: BotSlugTokenRequest):
    """
    Mint a LiveKit access token for a specific deployed bot.
    No user authentication required — the bot slug is the access key.
    """
    from app.modules.voice.application.session_launcher import start_session

    bot = await _bot_repo.get_by_slug(slug)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    # Load realtime config
    config = await _config_repo.get_active()
    if not config:
        raise HTTPException(503, "Realtime transport not configured")

    try:
        api_key = await _decrypt_value(config["encrypted_api_key"])
        api_secret = await _decrypt_value(config["encrypted_api_secret"])
    except Exception as e:
        logger.error("[TOKEN] Failed to decrypt realtime credentials: %s", e)
        raise HTTPException(500, "Configuration error")

    # Load speech providers
    stt_provider = None
    if bot.get("stt_provider_id"):
        stt_provider = await _speech_repo.get_by_id(bot["stt_provider_id"])
    tts_provider = None
    if bot.get("tts_provider_id"):
        tts_provider = await _speech_repo.get_by_id(bot["tts_provider_id"])

    # Load LLM provider
    llm_provider = None
    if bot.get("llm_provider_id"):
        llm_provider = await _llm_repo.get_by_id(bot["llm_provider_id"])

    # Create session
    session_id = str(uuid.uuid4())
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    await _session_repo.create(
        session_id=session_id,
        conversation_type=req.conversation_type,
        user_id=user_id,
        bot_id=bot["id"],
    )

    # Mint LiveKit token
    room_name = f"session-{session_id}"
    ttl = config.get("room_token_ttl_seconds", 3600)

    try:
        from livekit.api import AccessToken, VideoGrants
        from datetime import timedelta

        token = AccessToken(api_key=api_key, api_secret=api_secret)
        token.with_identity(user_id)
        import json

        token.with_metadata(
            json.dumps({"session_id": session_id, "bot_id": bot["id"]})
        )
        token.with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        token.with_ttl(timedelta(seconds=ttl))
        jwt_token = token.to_jwt()
    except Exception as e:
        logger.error("[TOKEN] Failed to mint access token: %s", e)
        raise HTTPException(500, "Token generation failed")

    # Start LiveKit session adapter as background task
    task = asyncio.create_task(
        start_session(
            session_id=session_id,
            room_name=room_name,
            server_url=config["server_url"],
            api_key=api_key,
            api_secret=api_secret,
            bot=bot,
            stt_provider=stt_provider,
            tts_provider=tts_provider,
            llm_provider=llm_provider,
            audio_sample_rate=config.get("audio_sample_rate", 16000),
        )
    )
    def _on_session_task_done(t, sid=session_id):
        if not t.cancelled():
            exc = t.exception()
            if exc:
                logger.error("[TOKEN] Background session task failed for session=%s: %s", sid, exc)
    task.add_done_callback(_on_session_task_done)

    logger.info(
        "[TOKEN] Minted bot-slug token for session=%s bot=%s", session_id, bot["name"]
    )

    return {
        "token": jwt_token,
        "room_name": room_name,
        "server_url": config["server_url"],
        "session_id": session_id,
        "bot_name": bot.get("name", "Assistant"),
    }
