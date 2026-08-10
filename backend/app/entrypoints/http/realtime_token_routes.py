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


@router.post("/token")
async def mint_realtime_token(req: TokenRequest, authorization: str = ""):
    """
    Mint a realtime access token for the current user.
    Creates a new session and starts the LiveKit session adapter.
    """
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
        logger.error(f"[TOKEN] Failed to decrypt realtime credentials: {e}")
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
        from datetime import timedelta
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

    logger.info(f"[TOKEN] Minted token for session={session_id} room={room_name}")

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
        # STT credentials — pass encrypted blob to factory (factory decrypts)
        stt_cred_blob = {}
        stt_kv = 1
        if stt_provider and stt_provider.get("credentials_enc"):
            stt_cred_blob = stt_provider["credentials_enc"]
            stt_kv = stt_provider.get("key_version", 1)

        # TTS credentials — pass encrypted blob to factory (factory decrypts)
        tts_cred_blob = {}
        tts_kv = 1
        if tts_provider and tts_provider.get("credentials_enc"):
            tts_cred_blob = tts_provider["credentials_enc"]
            tts_kv = tts_provider.get("key_version", 1)

        # Decrypt LLM provider credentials
        llm_creds = {}
        if llm_provider and llm_provider.get("credentials_enc"):
            llm_creds = await load_and_decrypt(
                llm_provider["credentials_enc"],
                llm_provider.get("key_version", 1),
            )

        # Build snapshot — use bot-level model/language, falling back to provider defaults
        snapshot = SessionSnapshot(
            session_id=session_id,
            bot_id=bot["id"],
            bot_name=bot.get("name", "Assistant"),
            bot_description=bot.get("description", ""),
            system_prompt=bot.get("system_prompt", ""),
            greeting=bot.get("greeting", ""),
            stt_provider_type=stt_provider.get("provider_type", "") if stt_provider else "",
            stt_model=bot.get("stt_model") or (stt_provider.get("stt_model", "") if stt_provider else ""),
            stt_language=bot.get("stt_primary_language", "en"),
            stt_languages=bot.get("stt_languages", ["en"]),
            stt_primary_language=bot.get("stt_primary_language", "en"),
            tts_provider_type=tts_provider.get("provider_type", "") if tts_provider else "",
            tts_model=bot.get("tts_model") or (tts_provider.get("tts_model", "") if tts_provider else ""),
            tts_voice_id=tts_provider.get("tts_voice_id", "") if tts_provider else "",
            tts_language=bot.get("tts_primary_language", "en"),
            tts_languages=bot.get("tts_languages", ["en"]),
            tts_primary_language=bot.get("tts_primary_language", "en"),
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

        # Create and connect room
        from livekit import rtc
        from livekit.agents.utils import http_context

        room = rtc.Room()
        disconnected_event = asyncio.Event()

        @room.on("disconnected")
        def _on_disconnect(*args, **kwargs):
            disconnected_event.set()

        # Generate a server-side token for the agent
        from livekit.api import AccessToken, VideoGrants

        agent_token = AccessToken(api_key=api_key, api_secret=api_secret)
        agent_token.with_identity(f"agent-{session_id}")
        agent_token.with_grants(VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=True,
            can_subscribe=True,
        ))
        from datetime import timedelta
        agent_token.with_ttl(timedelta(seconds=7200))
        agent_jwt = agent_token.to_jwt()

        async with http_context.open():
            await room.connect(server_url, agent_jwt)
            logger.info(f"[SESSION] Agent connected to room={room_name}")

            # Create and start session
            session = LiveKitSession(snapshot=snapshot)
            await session.start(room)

            # Keep session alive until room disconnects
            await disconnected_event.wait()

    except Exception as e:
        logger.error(f"[SESSION] Session adapter failed for {session_id}: {e}")
    finally:
        if 'session' in locals():
            try:
                await session.destroy()
            except Exception:
                pass
