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


@router.get("/{slug}")
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


@router.post("/{slug}/token")
async def mint_token_for_bot(slug: str, req: BotSlugTokenRequest):
    """
    Mint a LiveKit access token for a specific deployed bot.
    No user authentication required — the bot slug is the access key.
    """
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
        logger.error(f"[TOKEN] Failed to decrypt realtime credentials: {e}")
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
        logger.error(f"[TOKEN] Failed to mint access token: {e}")
        raise HTTPException(500, "Token generation failed")

    # Start LiveKit session adapter as background task
    asyncio.create_task(
        _start_session_adapter(
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

    logger.info(
        f"[TOKEN] Minted bot-slug token for session={session_id} bot={bot['name']}"
    )

    return {
        "token": jwt_token,
        "room_name": room_name,
        "server_url": config["server_url"],
        "session_id": session_id,
        "bot_name": bot.get("name", "Assistant"),
    }


async def _start_session_adapter(
    session_id: str,
    room_name: str,
    server_url: str,
    api_key: str,
    api_secret: str,
    bot: dict,
    stt_provider: dict,
    tts_provider: dict,
    llm_provider: dict,
    audio_sample_rate: int,
):
    """Start the LiveKit session adapter for a conversation session."""
    from app.modules.voice.infrastructure.external.livekit_session_adapter import (
        LiveKitSession,
        SessionSnapshot,
    )

    try:
        stt_cred_blob = {}
        stt_kv = 1
        if stt_provider and stt_provider.get("credentials_enc"):
            stt_cred_blob = stt_provider["credentials_enc"]
            stt_kv = stt_provider.get("key_version", 1)

        tts_cred_blob = {}
        tts_kv = 1
        if tts_provider and tts_provider.get("credentials_enc"):
            tts_cred_blob = tts_provider["credentials_enc"]
            tts_kv = tts_provider.get("key_version", 1)

        llm_creds = {}
        if llm_provider and llm_provider.get("credentials_enc"):
            llm_creds = await load_and_decrypt(
                llm_provider["credentials_enc"],
                llm_provider.get("key_version", 1),
            )

        # Detect when tts_model is actually a voice profile ID rather than an engine model:
        # - Fish Audio voice profiles: 24-char hex (MongoDB ObjectIds)
        # - ElevenLabs voice profiles: 20-char alphanumeric (not starting with eleven_ or scribe_)
        bot_tts_model = bot.get("tts_model", "")
        bot_tts_voice_id = ""
        if tts_provider and bot_tts_model:
            ptype = tts_provider.get("provider_type", "")
            if (ptype == "fishaudio"
                    and len(bot_tts_model) == 24
                    and all(c in "0123456789abcdef" for c in bot_tts_model.lower())):
                # Fish Audio voice profile → use as voice_id, fall back to provider engine model
                bot_tts_voice_id = bot_tts_model
                bot_tts_model = tts_provider.get("tts_model", "") or "s2.1-pro"
            elif (ptype == "elevenlabs"
                    and len(bot_tts_model) == 20
                    and bot_tts_model.isalnum()
                    and not bot_tts_model.startswith("eleven_")
                    and not bot_tts_model.startswith("scribe_")):
                # ElevenLabs voice profile → use as voice_id, use default model
                bot_tts_voice_id = bot_tts_model
                bot_tts_model = ""

        snapshot = SessionSnapshot(
            session_id=session_id,
            bot_id=bot["id"],
            bot_name=bot.get("name", "Assistant"),
            bot_description=bot.get("description", ""),
            system_prompt=bot.get("system_prompt", ""),
            greeting=bot.get("greeting", ""),
            stt_provider_type=(
                stt_provider.get("provider_type", "") if stt_provider else ""
            ),
            stt_model=bot.get("stt_model") or (stt_provider.get("stt_model", "") if stt_provider else ""),
            stt_language=bot.get("stt_primary_language", "en"),
            stt_languages=bot.get("stt_languages", ["en"]),
            stt_primary_language=bot.get("stt_primary_language", "en"),
            tts_provider_type=(
                tts_provider.get("provider_type", "") if tts_provider else ""
            ),
            tts_model=bot_tts_model or bot.get("tts_model") or (tts_provider.get("tts_model", "") if tts_provider else ""),
            tts_voice_id=bot_tts_voice_id or (tts_provider.get("tts_voice_id", "") if tts_provider else ""),
            tts_language=bot.get("tts_primary_language", "en"),
            tts_languages=bot.get("tts_languages", ["en"]),
            tts_primary_language=bot.get("tts_primary_language", "en"),
            tts_custom_model=bot.get("tts_custom_model", ""),
            tts_custom_voice_id=bot.get("tts_custom_voice_id", ""),
            tts_custom_endpoint=bot.get("tts_custom_endpoint", ""),
            llm_provider_id=bot.get("llm_provider_id", ""),
            llm_model=bot.get("llm_model", ""),
            server_url=server_url,
            room_name=room_name,
            audio_sample_rate=audio_sample_rate,
            llm_api_key=llm_creds.get("api_key", ""),
            llm_base_url=llm_provider.get("base_url", "") if llm_provider else "",
            encrypted_stt_credentials=stt_cred_blob,
            stt_key_version=stt_kv,
            encrypted_tts_credentials=tts_cred_blob,
            tts_key_version=tts_kv,
        )

        from livekit import rtc
        from livekit.agents.utils import http_context

        room = rtc.Room()
        disconnected_event = asyncio.Event()

        @room.on("disconnected")
        def _on_disconnect(*args, **kwargs):
            disconnected_event.set()

        from livekit.api import AccessToken, VideoGrants
        from datetime import timedelta

        agent_token = AccessToken(api_key=api_key, api_secret=api_secret)
        agent_token.with_identity(f"agent-{session_id}")
        agent_token.with_grants(
            VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            )
        )
        agent_token.with_ttl(timedelta(seconds=7200))
        agent_jwt = agent_token.to_jwt()

        async with http_context.open():
            await room.connect(server_url, agent_jwt)
            logger.info(f"[SESSION] Agent connected to room={room_name}")

            session = LiveKitSession(snapshot=snapshot)
            await session.start(room)

            await disconnected_event.wait()

    except Exception as e:
        logger.error(f"[SESSION] Session adapter failed for {session_id}: {e}")
    finally:
        if "session" in locals():
            try:
                await session.destroy()
            except Exception:
                pass
