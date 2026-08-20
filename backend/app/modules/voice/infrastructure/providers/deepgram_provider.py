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
        from app.shared.config.knobs import knobs

        api_key: str = creds["api_key"]
        model: str = config.get("stt_model") or knobs.deepgram_stt.default_model
        language: str = config.get("stt_language") or "en"
        language = _LANG_MAP.get(language, language)

        # Deepgram STT model normalization (protect against non-existent model strings)
        if model == "nova-3-multilingual":
            model = "nova-3" if language.startswith("en") else "nova-2-general"
            logger.info("[DEEPGRAM] Remapped 'nova-3-multilingual' -> '%s' for language '%s'", model, language)
        elif model == "nova-3-medical":
            model = "nova-2-medical"
            logger.info("[DEEPGRAM] Remapped 'nova-3-medical' -> 'nova-2-medical'")

        logger.info("[DEEPGRAM] STT  model=%s  language=%s", model, language)
        stt_kwargs: Dict[str, Any] = {
            "api_key": api_key,
            "model": model,
            "language": language,
            "smart_format": knobs.deepgram_stt.smart_format,
            "punctuate": knobs.deepgram_stt.punctuate,
            "interim_results": knobs.deepgram_stt.interim_results,
            "endpointing_ms": knobs.deepgram_stt.endpointing_ms,
            "filler_words": knobs.deepgram_stt.filler_words,
            "no_delay": knobs.deepgram_stt.no_delay,
            "vad_events": knobs.deepgram_stt.vad_events,
            "sample_rate": knobs.deepgram_stt.sample_rate,
            "profanity_filter": knobs.deepgram_stt.profanity_filter,
        }
        if knobs.deepgram_stt.redact:
            stt_kwargs["redact"] = knobs.deepgram_stt.redact
        return _dg.STT(**stt_kwargs)

    def build_tts(self, config: Dict[str, Any], creds: Dict[str, Any]) -> Any:
        from livekit.plugins import deepgram as _dg
        from app.shared.config.knobs import knobs

        api_key: str = creds["api_key"]
        model: str = config.get("tts_custom_model") or config.get("tts_model") or knobs.deepgram_tts.default_model

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
                    mapped = knobs.deepgram_tts.default_model
            logger.info("[DEEPGRAM] TTS mapping '%s' -> '%s'", model, mapped)
            model = mapped
        elif model.startswith("aura-"):
            # Aura and Aura-2 models are used as-is
            pass
        else:
            logger.warning("[DEEPGRAM] Unknown TTS model '%s', defaulting to '%s'", model, knobs.deepgram_tts.default_model)
            model = knobs.deepgram_tts.default_model

        logger.info("[DEEPGRAM] TTS  model=%s", model)
        return _dg.TTS(
            api_key=api_key,
            model=model,
            sample_rate=knobs.deepgram_tts.sample_rate,
            encoding=knobs.deepgram_tts.encoding,
        )
