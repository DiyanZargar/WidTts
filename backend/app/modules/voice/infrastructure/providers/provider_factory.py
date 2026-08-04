"""
Speech Provider Factory.

Builds STT and TTS adapters from a speech provider config,
dispatching to Deepgram or ElevenLabs based on provider_type.
"""

import logging
from typing import Dict, Any

from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface

logger = logging.getLogger("provider_factory")


class SpeechProviderFactory:
    """
    Factory that builds STT/TTS adapters from a speech provider config dict.

    Expected config shape:
    {
        "provider_type": "deepgram" | "elevenlabs",
        "credentials": {"api_key": "...", ...},
        "stt_model": "nova-2",
        "stt_language": "en",
        "stt_extra": {},
        "tts_model": "flux-rufus-en",
        "tts_voice_id": "...",
        "tts_extra": {},
    }
    """

    @staticmethod
    def build_stt(config: Dict[str, Any]) -> STTProviderInterface:
        provider_type = config["provider_type"]
        creds = config["credentials"]

        if provider_type == "deepgram":
            from app.modules.voice.infrastructure.providers.deepgram.deepgram_stt_adapter import DeepgramSTTAdapter

            api_key = creds["api_key"]
            model = config.get("stt_model", "nova-2")
            extra = config.get("stt_extra", {})

            # Build STT URL from config
            base_url = extra.get("base_url", "wss://api.deepgram.com/v1/listen")
            if "flux" in model.lower():
                base_url = extra.get("base_url", "wss://api.deepgram.com/v2/listen")

            endpointing = extra.get("endpointing_ms", 300)
            punctuate = extra.get("punctuate", "true")
            interim = extra.get("interim_results", "true")
            smart_format = extra.get("smart_formatting", "true")

            stt_url = (
                f"{base_url}?model={model}"
                f"&punctuate={punctuate}"
                f"&interim_results={interim}"
                f"&endpointing={endpointing}"
                f"&smart_format={smart_format}"
            )

            logger.info(f"[FACTORY] Building Deepgram STT: model={model}")
            return DeepgramSTTAdapter(api_key=api_key, stt_url=stt_url)

        elif provider_type == "elevenlabs":
            from app.modules.voice.infrastructure.providers.elevenlabs.elevenlabs_stt_adapter import ElevenLabsSTTAdapter

            api_key = creds["api_key"]
            model = config.get("stt_model", "scribe_v1")
            language = config.get("stt_language", "en")

            logger.info(f"[FACTORY] Building ElevenLabs STT: model={model}")
            return ElevenLabsSTTAdapter(api_key=api_key, model_id=model, language=language)

        else:
            raise ValueError(f"Unknown speech provider type: {provider_type}")

    @staticmethod
    def build_tts(config: Dict[str, Any]) -> TTSProviderInterface:
        provider_type = config["provider_type"]
        creds = config["credentials"]

        if provider_type == "deepgram":
            from app.modules.voice.infrastructure.providers.deepgram.deepgram_tts_adapter import DeepgramTTSAdapter

            api_key = creds["api_key"]
            model = config.get("tts_model", "aura-asteria-en")

            logger.info(f"[FACTORY] Building Deepgram TTS: model={model}")
            return DeepgramTTSAdapter(api_key=api_key, tts_model=model)

        elif provider_type == "elevenlabs":
            from app.modules.voice.infrastructure.providers.elevenlabs.elevenlabs_tts_adapter import ElevenLabsTTSAdapter

            api_key = creds["api_key"]
            voice_id = config.get("tts_voice_id", "")
            model = config.get("tts_model", "eleven_turbo_v2_5")
            extra = config.get("tts_extra", {})

            if not voice_id:
                raise ValueError("ElevenLabs TTS requires tts_voice_id")

            logger.info(f"[FACTORY] Building ElevenLabs TTS: voice={voice_id}, model={model}")
            return ElevenLabsTTSAdapter(
                api_key=api_key,
                voice_id=voice_id,
                model_id=model,
                output_format=extra.get("output_format", "pcm_24000"),
                stability=extra.get("stability", 0.5),
                similarity_boost=extra.get("similarity_boost", 0.75),
            )

        else:
            raise ValueError(f"Unknown speech provider type: {provider_type}")
