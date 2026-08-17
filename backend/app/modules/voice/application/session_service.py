"""Session Service — Single source of truth for voice session creation.

Consolidates the duplicate token minting, provider lookup, and session
launch orchestration that was previously copy-pasted across
``public_bot_routes.py`` and ``realtime_token_routes.py``.

Both route files now delegate here, eliminating divergence risk.
"""

from __future__ import annotations

import uuid
import json
import asyncio
import logging
from typing import Dict, Any, Optional

from app.modules.session.infrastructure.persistence.session_repository import (
    SessionRepository,
)
from app.modules.provider.infrastructure.persistence.speech_provider_repository import (
    SpeechProviderRepository,
)
from app.modules.provider.infrastructure.persistence.llm_provider_repository import (
    LLMProviderRepository,
)
from app.shared.security.envelope_encryption import load_and_decrypt
from app.shared.schemas import TokenResponse

logger = logging.getLogger("session_service")

_session_repo = SessionRepository()
_speech_repo = SpeechProviderRepository()
_llm_repo = LLMProviderRepository()


async def _decrypt_value(encrypted: dict) -> str:
    """Decrypt a single encrypted value blob."""
    blob = encrypted["blob"]
    kv = encrypted["key_version"]
    result = await load_and_decrypt(blob, kv)
    return result["value"]


async def create_voice_session(
    *,
    bot: Dict[str, Any],
    user_id: str,
    conversation_type: str,
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Create a voice session, mint a LiveKit token, and start the background agent.

    Parameters
    ----------
    bot : dict
        The bot row from the database.
    user_id : str
        The user identity for the LiveKit token.
    conversation_type : str
        Session type (e.g. "active_bot", "bot_session").
    config : dict
        The active realtime runtime config row with decrypted transport keys.

    Returns
    -------
    dict matching TokenResponse schema.
    """
    from app.modules.voice.application.session_launcher import start_session
    from livekit.api import AccessToken, VideoGrants
    from datetime import timedelta

    # Decrypt transport credentials
    try:
        api_key = await _decrypt_value(config["encrypted_api_key"])
        api_secret = await _decrypt_value(config["encrypted_api_secret"])
    except Exception as e:
        logger.error("[SESSION_SERVICE] Failed to decrypt realtime credentials: %s", e)
        raise ValueError("Configuration error: failed to decrypt transport credentials") from e

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
        conversation_type=conversation_type,
        user_id=user_id,
        bot_id=bot["id"],
    )

    # Mint LiveKit token
    room_name = f"session-{session_id}"
    ttl = config.get("room_token_ttl_seconds", 3600)

    try:
        token = AccessToken(api_key=api_key, api_secret=api_secret)
        token.with_identity(user_id)
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
        logger.error("[SESSION_SERVICE] Failed to mint access token: %s", e)
        raise ValueError("Token generation failed") from e

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
                logger.error("[SESSION_SERVICE] Background session task failed for session=%s: %s", sid, exc)

    task.add_done_callback(_on_session_task_done)

    logger.info("[SESSION_SERVICE] Created session=%s for bot=%s user=%s", session_id, bot.get("name"), user_id)

    return {
        "token": jwt_token,
        "room_name": room_name,
        "server_url": config["server_url"],
        "session_id": session_id,
        "bot_name": bot.get("name", "Assistant"),
    }
