"""
Realtime Token route.

Mints a LiveKit AccessToken scoped to a per-session room.
Also starts the LiveKit session adapter as a background task.
No LiveKit terminology appears in any response field name.
"""

import uuid
import logging
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.shared.security.token_service import verify_token, AuthenticationError
from app.shared.security.envelope_encryption import load_and_decrypt
from app.modules.voice.infrastructure.persistence.realtime_config_repository import (
    RealtimeConfigRepository,
)
from app.modules.session.infrastructure.persistence.postgres_session_repository import (
    PostgresSessionRepository,
)
from app.modules.bot.infrastructure.persistence.postgres_bot_repository import (
    PostgresBotRepository,
)
from app.modules.provider.infrastructure.persistence.postgres_speech_provider_repository import (
    PostgresSpeechProviderRepository,
)
from app.modules.provider.infrastructure.persistence.postgres_llm_provider_repository import (
    PostgresLLMProviderRepository,
)
from app.shared.schemas import TokenResponse

logger = logging.getLogger("realtime_token")
router = APIRouter(prefix="/realtime", tags=["realtime"])

_config_repo = RealtimeConfigRepository()
_session_repo = PostgresSessionRepository()
_bot_repo = PostgresBotRepository()
_speech_repo = PostgresSpeechProviderRepository()
_llm_repo = PostgresLLMProviderRepository()


async def _decrypt_value(encrypted: dict) -> str:
    blob = encrypted["blob"]
    kv = encrypted["key_version"]
    result = await load_and_decrypt(blob, kv)
    return result["value"]


class TokenRequest(BaseModel):
    conversation_type: str = "active_bot"


@router.post("/token", response_model=TokenResponse)
async def mint_realtime_token(req: TokenRequest, authorization: str = ""):
    """
    Mint a realtime access token for the current user.
    Creates a new session and starts the LiveKit session adapter.
    """
    from app.modules.voice.application.session_launcher import start_session

    # Authenticate user
    token_str = authorization.replace("Bearer ", "") if authorization else None
    try:
        user_id = verify_token(token_str)
    except AuthenticationError as e:
        raise HTTPException(401, f"Authentication failed: {e}")

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

    # Load active bot
    bot = await _bot_repo.get_active()
    if not bot:
        raise HTTPException(503, "No active bot configured")

    # Load speech providers (STT and TTS can be different)
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

        token.with_metadata(json.dumps({"session_id": session_id, "bot_id": bot["id"]}))
        token.with_grants(VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
            can_publish_data=True,
        ))
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

    logger.info("[TOKEN] Minted token for session=%s room=%s", session_id, room_name)

    return {
        "token": jwt_token,
        "room_name": room_name,
        "server_url": config["server_url"],
        "session_id": session_id,
        "bot_name": bot.get("name", "Assistant"),
    }
