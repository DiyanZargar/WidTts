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
        model: str = config.get("stt_model") or "nova-3"
        language: str = config.get("stt_language") or "en"
        # Map common short codes to Deepgram-expected codes
        lang_map = {
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
        language = lang_map.get(language, language)

        logger.info("[PLUGIN_FACTORY] Deepgram STT  model=%s  language=%s", model, language)
        return _dg.STT(
            api_key=api_key,
            model=model,
            language=language,
            smart_format=True,
            punctuate=True,
            interim_results=True,
            endpointing_ms=100,
        )

    elif provider_type == "elevenlabs":
        from livekit.plugins import elevenlabs as _el

        api_key: str = creds["api_key"]
        model_id: str = config.get("stt_model") or "scribe_v1"
        language: str = config.get("stt_language") or ""
        logger.info("[PLUGIN_FACTORY] ElevenLabs STT  model_id=%s  language=%s", model_id, language)
        kwargs = {"api_key": api_key, "model_id": model_id}
        if language:
            kwargs["language_code"] = language
        return _el.STT(**kwargs)

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
        model: str = config.get("tts_custom_model") or config.get("tts_model") or "aura-asteria-en"

        # Map flux-* model names to valid Deepgram Aura voices for LiveKit
        if model.startswith("flux-"):
            flux_map = {
                "flux-rufus-en": "aura-orion-en",
                "flux-aura-en": "aura-asteria-en",
                "flux-asteria-en": "aura-asteria-en",
                "flux-orion-en": "aura-orion-en",
                "flux-luna-en": "aura-luna-en",
                "flux-arcas-en": "aura-arcas-en",
                "flux-stella-en": "aura-stella-en",
                "flux-athena-en": "aura-athena-en",
                "flux-helios-en": "aura-helios-en",
                "flux-zeus-en": "aura-zeus-en",
            }
            mapped = flux_map.get(model)
            if mapped is None:
                # Try generic flux-X → aura-X mapping for any new flux voices
                candidate = "aura-" + model[5:]
                if candidate.startswith("aura-"):
                    mapped = candidate
                    logger.info("[PLUGIN_FACTORY] Flux model '%s' not in map, trying '%s'", model, mapped)
                else:
                    mapped = "aura-asteria-en"
            logger.info("[PLUGIN_FACTORY] Deepgram TTS mapping '%s' -> '%s'", model, mapped)
            model = mapped
        elif model.startswith("aura-"):
            # Aura and Aura-2 models are used as-is
            pass
        else:
            logger.warning("[PLUGIN_FACTORY] Unknown Deepgram TTS model '%s', defaulting to 'aura-asteria-en'", model)
            model = "aura-asteria-en"

        logger.info("[PLUGIN_FACTORY] Deepgram TTS  model=%s  language=%s", model, config.get("tts_language", ""))
        return _dg.TTS(api_key=api_key, model=model)

    elif provider_type == "elevenlabs":
        from livekit.plugins import elevenlabs as _el

        api_key: str = creds["api_key"]
        voice_id: str = config.get("tts_custom_voice_id") or config.get("tts_voice_id") or ""

        # Extract 20-char voice ID from tts_model if passed there
        if not voice_id and config.get("tts_model"):
            m = config["tts_model"]
            if len(m) == 20 and m.isalnum() and not m.startswith("eleven_") and not m.startswith("scribe_"):
                voice_id = m

        # Fallback to Sarah (EXAVITQu4vr4xnSDxMaL) which is available on all tiers
        voice_id = voice_id or "EXAVITQu4vr4xnSDxMaL"

        language: str = config.get("tts_language") or ""
        logger.info("[PLUGIN_FACTORY] ElevenLabs TTS  voice_id=%s  language=%s", _mask(voice_id), language)
        kwargs = {"api_key": api_key, "voice_id": voice_id}
        if language:
            kwargs["language"] = language
        return _el.TTS(**kwargs)

    elif provider_type == "fishaudio":
        api_key: str = creds["api_key"]
        model: str = config.get("tts_custom_model") or config.get("tts_model") or "s2.1-pro"
        reference_id: str = config.get("tts_custom_voice_id") or config.get("tts_voice_id") or ""
        language: str = config.get("tts_language") or ""
        custom_endpoint: str = config.get("tts_custom_endpoint") or ""

        logger.info("[PLUGIN_FACTORY] Fish Audio TTS  model=%s  reference_id=%s  language=%s  endpoint=%s",
                     model, _mask(reference_id), language, custom_endpoint or "(default)")
        return _build_fish_audio_tts(api_key, model, reference_id, language, custom_endpoint)

    else:
        raise UnsupportedProviderError(
            f"Unsupported speech provider type for TTS: {provider_type!r}"
        )


# ── Fish Audio custom TTS adapter ───────────────────────────────────

def _build_fish_audio_tts(
    api_key: str, model: str, reference_id: str, language: str, custom_endpoint: str = ""
) -> "FishAudioTTS":
    """Build a custom LiveKit-compatible TTS instance for Fish Audio."""
    return FishAudioTTS(
        api_key=api_key,
        model=model,
        reference_id=reference_id,
        language=language,
        custom_endpoint=custom_endpoint,
    )


# Import LiveKit TTS base class for FishAudioTTS inheritance
from livekit.agents.tts import TTS as _LiveKitTTS, TTSCapabilities, ChunkedStream  # noqa: E402


class FishAudioTTS(_LiveKitTTS):
    """Custom LiveKit-compatible TTS wrapper for Fish Audio REST API.

    Fish Audio has no official LiveKit plugin, so this implements the
    ``livekit.agents.tts.TTS`` interface (``synthesize()`` returns a
    ``ChunkedStream``) by calling their HTTP API and decoding the mp3
    response via the LiveKit AudioEmitter's built-in mp3 codec support.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "s2.1-pro",
        reference_id: str = "",
        language: str = "",
        custom_endpoint: str = "",
    ) -> None:
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=24000,
            num_channels=1,
        )
        self._api_key = api_key
        self._model = model
        self._reference_id = reference_id
        self._language = language
        self._custom_endpoint = custom_endpoint
        self._session = None  # lazily created aiohttp session

    # -- LiveKit TTS interface compatibility --

    def synthesize(self, text: str, *, conn_options=None):
        if conn_options is None:
            from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS
            conn_options = DEFAULT_API_CONNECT_OPTIONS

        return _FishAudioChunkedStream(
            tts=self,
            input_text=text,
            conn_options=conn_options,
            api_key=self._api_key,
            model=self._model,
            reference_id=self._reference_id,
            language=self._language,
            custom_endpoint=self._custom_endpoint,
        )

    @property
    def model(self) -> str:
        return self._model

    @property
    def provider(self) -> str:
        return "Fish Audio"

    @property
    def label(self) -> str:
        return f"fishaudio.{self._model}"

    def _ensure_session(self):
        if self._session is None:
            import aiohttp
            self._session = aiohttp.ClientSession()
        return self._session

    def prewarm(self) -> None:
        pass

    async def aclose(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    # EventEmitter compatibility (AgentSession may call emit/on)
    _handlers: dict = {}

    def on(self, event: str, handler=None):
        if handler is None:
            def decorator(fn):
                self._handlers.setdefault(event, []).append(fn)
                return fn
            return decorator
        self._handlers.setdefault(event, []).append(handler)
        return handler

    def emit(self, event: str, *args, **kwargs):
        for handler in self._handlers.get(event, []):
            try:
                handler(*args, **kwargs)
            except Exception:
                pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.aclose()

    def __del__(self):
        # Best-effort cleanup
        if self._session and not self._session.closed:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
            except Exception:
                pass



class _FishAudioChunkedStream(ChunkedStream):
    """ChunkedStream-compatible wrapper that calls Fish Audio's REST API.

    Follows the same pattern as the Deepgram/ElevenLabs ChunkedStream:
    - ``_run(output_emitter)`` is called by the LiveKit framework
    - We POST to Fish Audio, get mp3 bytes, push to the emitter
    - The AudioEmitter handles mp3 -> PCM decoding internally
    """

    def __init__(
        self,
        *,
        tts: FishAudioTTS,
        input_text: str,
        conn_options,
        api_key: str,
        model: str,
        reference_id: str,
        language: str,
        custom_endpoint: str = "",
    ) -> None:
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._api_key = api_key
        self._model = model
        self._reference_id = reference_id
        self._language = language
        self._custom_endpoint = custom_endpoint

    @property
    def input_text(self) -> str:
        return self._input_text

    @property
    def done(self) -> bool:
        return True  # synchronous HTTP, done after _run completes

    @property
    def exception(self):
        return None

    async def _run(self, output_emitter) -> None:
        """Call Fish Audio REST API and push mp3 audio to the emitter."""
        import asyncio
        import aiohttp
        from livekit.agents import APIConnectionError, APITimeoutError, APIStatusError, utils

        try:
            session = self._tts._ensure_session()

            payload: dict = {"text": self._input_text}
            if self._reference_id:
                payload["reference_id"] = self._reference_id
            if self._language:
                payload["language"] = self._language

            # Fish Audio uses model in request header, not body
            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "model": self._model,
            }

            logger.info(
                "[PLUGIN_FACTORY] Fish Audio synthesize  model=%s  text_len=%d  endpoint=%s",
                self._model, len(self._input_text), self._custom_endpoint or "(default)",
            )

            timeout_sec = self._conn_options.timeout if self._conn_options else 15
            api_url = self._custom_endpoint.rstrip("/") + "/v1/tts" if self._custom_endpoint else "https://api.fish.audio/v1/tts"
            async with session.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30, sock_connect=timeout_sec),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise APIStatusError(
                        message=f"Fish Audio API error: {resp.status}",
                        status_code=resp.status,
                        request_id=None,
                        body=body[:200],
                    )

                # Initialize emitter with audio/mpeg — LiveKit's
                # AudioStreamDecoder will handle mp3 -> PCM conversion
                output_emitter.initialize(
                    request_id=utils.shortuuid(),
                    sample_rate=24000,
                    num_channels=1,
                    mime_type="audio/mpeg",
                )

                async for data, _ in resp.content.iter_chunks():
                    if data:
                        output_emitter.push(data)

                output_emitter.flush()

        except asyncio.TimeoutError:
            raise APITimeoutError() from None
        except aiohttp.ClientResponseError as e:
            raise APIStatusError(
                message=e.message, status_code=e.status, request_id=None, body=None
            ) from None
        except (APIConnectionError, APITimeoutError, APIStatusError):
            raise
        except Exception as e:
            raise APIConnectionError(message=str(e)) from e


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
