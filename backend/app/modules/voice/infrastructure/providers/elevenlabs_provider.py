"""ElevenLabs speech provider — STT and TTS plugin construction.

Maps generic config fields to ``livekit.plugins.elevenlabs.STT`` and
``livekit.plugins.elevenlabs.TTS`` with voice ID detection and language
passthrough.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.modules.voice.infrastructure.providers.base import BaseSpeechProvider, mask

logger = logging.getLogger("speech_provider.elevenlabs")


class ElevenLabsProvider(BaseSpeechProvider):
    """ElevenLabs STT & TTS provider using official LiveKit plugins."""

    def build_stt(self, config: Dict[str, Any], creds: Dict[str, Any]) -> Any:
        from livekit.plugins import elevenlabs as _el
        from app.shared.config.knobs import knobs

        api_key: str = creds["api_key"]
        model_id: str = config.get("stt_model") or knobs.elevenlabs_stt.default_model_id
        language: str = config.get("stt_language") or knobs.elevenlabs_stt.default_language
        logger.info("[ELEVENLABS] STT  model_id=%s  language=%s", model_id, language)
        kwargs = {"api_key": api_key, "model_id": model_id}
        if language:
            kwargs["language_code"] = language
        return _el.STT(**kwargs)

    def build_tts(self, config: Dict[str, Any], creds: Dict[str, Any]) -> Any:
        from livekit.plugins import elevenlabs as _el
        from app.shared.config.knobs import knobs

        api_key: str = creds["api_key"]
        voice_id: str = config.get("tts_custom_voice_id") or config.get("tts_voice_id") or ""

        # Extract 20-char voice ID from tts_model if passed there
        if not voice_id and config.get("tts_model"):
            m = config["tts_model"]
            if len(m) == 20 and m.isalnum() and not m.startswith("eleven_") and not m.startswith("scribe_"):
                voice_id = m

        # Fallback to default voice ID from knobs (Sarah) which is available on all tiers
        voice_id = voice_id or knobs.elevenlabs_tts.default_voice_id
        model = config.get("tts_custom_model") or config.get("tts_model") or knobs.elevenlabs_tts.default_model
        language: str = config.get("tts_language") or ""
        logger.info("[ELEVENLABS] TTS  voice_id=%s  language=%s", mask(voice_id), language)

        voice_settings = _el.VoiceSettings(
            stability=knobs.elevenlabs_tts.stability,
            similarity_boost=knobs.elevenlabs_tts.similarity_boost,
            style=knobs.elevenlabs_tts.style,
            speed=knobs.elevenlabs_tts.speed,
            use_speaker_boost=knobs.elevenlabs_tts.use_speaker_boost,
        )

        kwargs = {
            "api_key": api_key,
            "voice_id": voice_id,
            "model": model,
            "voice_settings": voice_settings,
            "auto_mode": knobs.elevenlabs_tts.auto_mode,
            "apply_text_normalization": knobs.elevenlabs_tts.apply_text_normalization,
            "inactivity_timeout": knobs.elevenlabs_tts.inactivity_timeout,
        }
        if language:
            kwargs["language"] = language
        return _el.TTS(**kwargs)
