"""
Session Launcher — shared logic for starting a LiveKit voice session.

Both the authenticated token route and the public bot-slug route delegate
here to start a voice session. This is the single source of truth for:
  - Credential preparation (STT/TTS encrypted blobs, LLM decryption)
  - Voice profile ID detection (Fish Audio 24-char hex, ElevenLabs 20-char)
  - SessionSnapshot construction
  - LiveKit room connection and agent session lifecycle
"""

import asyncio
import logging
from typing import Optional, Dict, Any

from app.shared.security.envelope_encryption import load_and_decrypt
from app.shared.config.settings import settings

logger = logging.getLogger("session_launcher")


def detect_voice_profile(
    tts_model: str,
    provider_type: str,
) -> tuple[str, str]:
    """Detect when tts_model is actually a voice profile ID.

    Returns (voice_id, engine_model). If the model is a profile ID,
    voice_id is set and engine_model falls back to the provider default.
    If not a profile ID, voice_id is "" and engine_model is the original value.

    Fish Audio voice profiles: 24-char hex (MongoDB ObjectIds)
    ElevenLabs voice profiles: 20-char alphanumeric (not starting with eleven_ or scribe_)
    """
    if not tts_model or not provider_type:
        return "", tts_model

    if (provider_type == "fishaudio"
            and len(tts_model) == 24
            and all(c in "0123456789abcdef" for c in tts_model.lower())):
        return tts_model, ""

    if (provider_type == "elevenlabs"
            and len(tts_model) == 20
            and tts_model.isalnum()
            and not tts_model.startswith("eleven_")
            and not tts_model.startswith("scribe_")):
        return tts_model, ""

    return "", tts_model


async def start_session(
    *,
    session_id: str,
    room_name: str,
    server_url: str,
    api_key: str,
    api_secret: str,
    bot: Dict[str, Any],
    stt_provider: Optional[Dict[str, Any]],
    tts_provider: Optional[Dict[str, Any]],
    llm_provider: Optional[Dict[str, Any]],
    audio_sample_rate: int,
) -> None:
    """Start a LiveKit voice session for the given bot.

    This is the shared implementation used by both realtime_token_routes
    (authenticated, active bot) and public_bot_routes (by slug).

    Runs as a background task — exceptions are caught and logged.
    """
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

        # Detect voice profile IDs vs engine model names
        bot_tts_model = bot.get("tts_model", "")
        tts_provider_type = tts_provider.get("provider_type", "") if tts_provider else ""
        bot_tts_voice_id, resolved_model = detect_voice_profile(
            bot_tts_model, tts_provider_type,
        )
        if bot_tts_voice_id and not resolved_model:
            # Voice profile detected with no engine model — use provider default
            resolved_model = (tts_provider.get("tts_model", "") if tts_provider else "") or "s2.1-pro"

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
            tts_provider_type=tts_provider_type,
            tts_model=resolved_model or bot.get("tts_model") or (tts_provider.get("tts_model", "") if tts_provider else ""),
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
        from livekit.api import AccessToken, VideoGrants
        from datetime import timedelta

        room = rtc.Room()
        disconnected_event = asyncio.Event()

        @room.on("disconnected")
        def _on_disconnect(*args, **kwargs):
            disconnected_event.set()

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
        agent_token.with_ttl(timedelta(seconds=settings.agent_token_ttl_seconds))
        agent_jwt = agent_token.to_jwt()

        async with http_context.open():
            await room.connect(server_url, agent_jwt)
            logger.info("[SESSION] Agent connected to room=%s", room_name)

            session = LiveKitSession(snapshot=snapshot)
            await session.start(room)

            await disconnected_event.wait()

    except Exception as e:
        logger.error("[SESSION] Session adapter failed for %s: %s", session_id, e)
    finally:
        if "session" in locals():
            try:
                await session.destroy()
            except Exception:
                pass
