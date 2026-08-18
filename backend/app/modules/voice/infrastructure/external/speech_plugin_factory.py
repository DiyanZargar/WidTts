"""Speech Plugin Factory — Clean Registry Dispatcher.

Constructs official LiveKit plugin STT/TTS instances by delegating to
the appropriate speech provider strategy (Deepgram, ElevenLabs, Fish Audio).

This is the **only** place in the codebase that maps provider names to
concrete provider implementations. Business logic never imports livekit
plugins directly — it receives already-constructed plugin instances.

Design notes:
- Provider implementations live in ``providers/`` as isolated modules.
- Adding a new provider requires: (1) create ``providers/newprovider.py``,
  (2) register it in ``_PROVIDERS`` below. Zero edits to existing providers.
- Credentials are decrypted via envelope_encryption at construction
  time and never logged.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.modules.voice.infrastructure.providers.base import (
    BaseSpeechProvider,
    UnsupportedProviderError,
    mask_credentials,
)
from app.modules.voice.infrastructure.providers.deepgram_provider import DeepgramProvider
from app.modules.voice.infrastructure.providers.elevenlabs_provider import ElevenLabsProvider
from app.modules.voice.infrastructure.providers.fish_audio_provider import FishAudioProvider

logger = logging.getLogger("speech_plugin_factory")

# ── Provider Registry ────────────────────────────────────────────────
# To add a new provider, create providers/newprovider.py implementing
# BaseSpeechProvider and register it here. Nothing else changes.

_PROVIDERS: Dict[str, BaseSpeechProvider] = {
    "deepgram": DeepgramProvider(),
    "elevenlabs": ElevenLabsProvider(),
    "fishaudio": FishAudioProvider(),
}


# ── Public factory API ───────────────────────────────────────────────

async def build_stt_plugin(config: Dict[str, Any]) -> Any:
    """
    Construct an official LiveKit STT plugin from a speech provider config.

    Parameters
    ----------
    config : dict
        A row from ``speech_providers`` with at least::

            {
                "provider_type": "deepgram" | "elevenlabs",
                "credentials_enc": { "nonce": "…", "ciphertext": "…" },
                "key_version": int,
                "stt_model": str | None,
                "stt_language": str | None,
            }

    Returns
    -------
    A livekit STT plugin instance (e.g. ``livekit.plugins.deepgram.STT``).
    """
    provider_type = config["provider_type"]
    creds = await _decrypt_credentials(config)
    masked = mask_credentials(creds)
    logger.info("[PLUGIN_FACTORY] build_stt  provider=%s  creds=%s", provider_type, masked)

    provider = _PROVIDERS.get(provider_type)
    if not provider:
        raise UnsupportedProviderError(
            f"Unsupported speech provider type for STT: {provider_type!r}"
        )
    return provider.build_stt(config, creds)


async def build_tts_plugin(config: Dict[str, Any]) -> Any:
    """
    Construct an official LiveKit TTS plugin from a speech provider config.

    Parameters
    ----------
    config : dict
        Same shape as :func:`build_stt_plugin`, plus::

            {
                "tts_model": str | None,
                "tts_voice_id": str | None,
            }

    Returns
    -------
    A livekit TTS plugin instance (e.g. ``livekit.plugins.deepgram.TTS``).
    """
    provider_type = config["provider_type"]
    creds = await _decrypt_credentials(config)
    masked = mask_credentials(creds)
    logger.info("[PLUGIN_FACTORY] build_tts  provider=%s  creds=%s", provider_type, masked)

    provider = _PROVIDERS.get(provider_type)
    if not provider:
        raise UnsupportedProviderError(
            f"Unsupported speech provider type for TTS: {provider_type!r}"
        )
    return provider.build_tts(config, creds)


# ── Internal helpers ─────────────────────────────────────────────────

async def _decrypt_credentials(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Decrypt the ``credentials_enc`` field using envelope encryption.

    Expects ``credentials_enc`` (JSONB blob) and ``key_version`` (int)
    to be present in the config dict.
    """
    from app.shared.security.envelope_encryption import load_and_decrypt

    credentials_enc: Dict[str, str] = config["credentials_enc"]
    key_version: int = config["key_version"]

    logger.debug(
        "[PLUGIN_FACTORY] Decrypting credentials  key_version=%s",
        key_version,
    )
    return await load_and_decrypt(credentials_enc, key_version)
