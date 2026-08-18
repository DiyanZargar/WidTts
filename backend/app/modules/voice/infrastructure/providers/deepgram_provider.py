"""Deepgram speech provider — STT and TTS plugin construction.

Maps generic config fields to ``livekit.plugins.deepgram.STT`` and
``livekit.plugins.deepgram.TTS`` with Flux-to-Aura voice mapping and
Deepgram-specific language code resolution.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.modules.voice.infrastructure.providers.base import BaseSpeechProvider
from app.shared.constants.model_catalogs import FLUX_TO_AURA_MAP

logger = logging.getLogger("speech_provider.deepgram")

# Map common short codes to Deepgram-expected codes
_LANG_MAP = {
    "en": "en-US", "es": "es", "fr": "fr", "de": "de", "pt": "pt",
    "zh": "zh", "ja": "ja", "ko": "ko", "hi": "hi", "ar": "ar",
    "ru": "ru", "it": "it", "nl": "nl", "pl": "pl", "tr": "tr",
    "sv": "sv", "no": "no", "da": "da", "fi": "fi", "cs": "cs",
    "el": "el", "he": "he", "th": "th", "vi": "vi", "id": "id",
    "ms": "ms", "ro": "ro", "hu": "hu", "uk": "uk", "ca": "ca",
    "tl": "tl", "bn": "bn", "ta": "ta", "te": "te", "ur": "ur",
    "fa": "fa", "hr": "hr", "sk": "sk", "sl": "sl", "sr": "sr",
    "bg": "bg", "lt": "lt", "lv": "lv", "et": "et",
}


class DeepgramProvider(BaseSpeechProvider):
    """Deepgram STT & TTS provider using official LiveKit plugins."""

    def build_stt(self, config: Dict[str, Any], creds: Dict[str, Any]) -> Any:
        from livekit.plugins import deepgram as _dg

        api_key: str = creds["api_key"]
        model: str = config.get("stt_model") or "nova-3"
        language: str = config.get("stt_language") or "en"
        language = _LANG_MAP.get(language, language)

        logger.info("[DEEPGRAM] STT  model=%s  language=%s", model, language)
        return _dg.STT(
            api_key=api_key,
            model=model,
            language=language,
            smart_format=True,
            punctuate=True,
            interim_results=True,
            endpointing_ms=400,
        )

    def build_tts(self, config: Dict[str, Any], creds: Dict[str, Any]) -> Any:
        from livekit.plugins import deepgram as _dg

        api_key: str = creds["api_key"]
        model: str = config.get("tts_custom_model") or config.get("tts_model") or "aura-asteria-en"

        # Map flux-* model names to valid Deepgram Aura voices for LiveKit
        if model.startswith("flux-"):
            mapped = FLUX_TO_AURA_MAP.get(model)
            if mapped is None:
                # Try generic flux-X → aura-X mapping for any new flux voices
                candidate = "aura-" + model[5:]
                if candidate.startswith("aura-"):
                    mapped = candidate
                    logger.info("[DEEPGRAM] Flux model '%s' not in map, trying '%s'", model, mapped)
                else:
                    mapped = "aura-asteria-en"
            logger.info("[DEEPGRAM] TTS mapping '%s' -> '%s'", model, mapped)
            model = mapped
        elif model.startswith("aura-"):
            # Aura and Aura-2 models are used as-is
            pass
        else:
            logger.warning("[DEEPGRAM] Unknown TTS model '%s', defaulting to 'aura-asteria-en'", model)
            model = "aura-asteria-en"

        logger.info("[DEEPGRAM] TTS  model=%s", model)
        return _dg.TTS(api_key=api_key, model=model)
