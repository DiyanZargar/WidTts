"""
Speech Plugin Factory.

Constructs official LiveKit plugin STT/TTS instances from a stored
speech provider config dict (as persisted in the `speech_providers`
table).

This is the **only** place in the codebase that maps provider names to
livekit.plugins.* classes.  Business logic never imports livekit plugins
directly — it receives already-constructed plugin instances.

Design notes:
- Lazy imports (inside each if-branch) so livekit plugins are never
  loaded at module import time.
- Credentials are decrypted via envelope_encryption at construction
  time and never logged.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger("speech_plugin_factory")


# ── Error types ──────────────────────────────────────────────────────

class UnsupportedProviderError(Exception):
    """Raised when the factory encounters an unknown provider_type."""


# ── Credential helpers ───────────────────────────────────────────────

def _mask(value: str, visible: int = 4) -> str:
    """Return a masked version of a secret for safe logging."""
    if not value or len(value) <= visible:
        return "****"
    return f"{value[:visible]}…(len={len(value)})"


def _mask_credentials(creds: Dict[str, Any]) -> Dict[str, str]:
    """Return a copy of creds with all values masked for logging."""
    return {k: _mask(str(v)) for k, v in creds.items()}


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
                "stt_extra": dict | None,
            }

    Returns
    -------
    A livekit STT plugin instance (e.g. ``livekit.plugins.deepgram.STT``).
    """
    provider_type = config["provider_type"]
    creds = await _decrypt_credentials(config)
    masked = _mask_credentials(creds)
    logger.info("[PLUGIN_FACTORY] build_stt  provider=%s  creds=%s", provider_type, masked)

    if provider_type == "deepgram":
        from livekit.plugins import deepgram as _dg

        api_key: str = creds["api_key"]
        model: str = config.get("stt_model") or "nova-2"

        logger.info("[PLUGIN_FACTORY] Deepgram STT  model=%s", model)
        return _dg.STT(api_key=api_key, model=model)

    elif provider_type == "elevenlabs":
        from livekit.plugins import elevenlabs as _el

        api_key: str = creds["api_key"]
        model_id: str = config.get("stt_model") or "scribe_v1"

        logger.info("[PLUGIN_FACTORY] ElevenLabs STT  model_id=%s", model_id)
        return _el.STT(api_key=api_key, model_id=model_id)

    else:
        raise UnsupportedProviderError(
            f"Unsupported speech provider type for STT: {provider_type!r}"
        )


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
                "tts_extra": dict | None,
            }

    Returns
    -------
    A livekit TTS plugin instance (e.g. ``livekit.plugins.deepgram.TTS``).
    """
    provider_type = config["provider_type"]
    creds = await _decrypt_credentials(config)
    masked = _mask_credentials(creds)
    logger.info("[PLUGIN_FACTORY] build_tts  provider=%s  creds=%s", provider_type, masked)

    if provider_type == "deepgram":
        from livekit.plugins import deepgram as _dg

        api_key: str = creds["api_key"]
        model: str = config.get("tts_model") or "aura-asteria-en"

        logger.info("[PLUGIN_FACTORY] Deepgram TTS  model=%s", model)
        return _dg.TTS(api_key=api_key, model=model)

    elif provider_type == "elevenlabs":
        from livekit.plugins import elevenlabs as _el

        api_key: str = creds["api_key"]
        voice_id: str = config.get("tts_voice_id") or ""

        if not voice_id:
            raise ValueError("ElevenLabs TTS requires tts_voice_id in the provider config")

        logger.info("[PLUGIN_FACTORY] ElevenLabs TTS  voice_id=%s", _mask(voice_id))
        return _el.TTS(api_key=api_key, voice_id=voice_id)

    else:
        raise UnsupportedProviderError(
            f"Unsupported speech provider type for TTS: {provider_type!r}"
        )


async def build_plugins(
    config: Dict[str, Any],
) -> Tuple[Any, Any]:
    """
    Convenience: build both STT and TTS plugins in one call.

    Returns (stt_plugin, tts_plugin).
    """
    stt = await build_stt_plugin(config)
    tts = await build_tts_plugin(config)
    return stt, tts


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
