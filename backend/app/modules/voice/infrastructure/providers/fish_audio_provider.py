"""Fish Audio speech provider — TTS-only plugin construction.

Fish Audio has no official LiveKit plugin, so this module contains the
complete custom ``FishAudioTTS`` class and ``_FishAudioChunkedStream``
that implement the ``livekit.agents.tts.TTS`` interface by calling the
Fish Audio HTTP REST API and streaming mp3 audio chunks.

This is the **only** file that changes when Fish Audio updates their API.
Deepgram and ElevenLabs are completely isolated.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.modules.voice.infrastructure.providers.base import (
    BaseSpeechProvider,
    UnsupportedProviderError,
    mask,
)
from app.shared.constants.provider_urls import FISH_AUDIO_API_URL

logger = logging.getLogger("speech_provider.fish_audio")


class FishAudioProvider(BaseSpeechProvider):
    """Fish Audio TTS-only provider using a custom LiveKit-compatible adapter."""

    def build_stt(self, config: Dict[str, Any], creds: Dict[str, Any]) -> Any:
        raise UnsupportedProviderError(
            "Unsupported speech provider type for STT: 'fishaudio'. Fish Audio does not support STT. Use Deepgram or ElevenLabs."
        )

    def build_tts(self, config: Dict[str, Any], creds: Dict[str, Any]) -> Any:
        from app.shared.config.knobs import knobs

        api_key: str = creds["api_key"]
        model: str = config.get("tts_custom_model") or config.get("tts_model") or knobs.fish_audio_tts.default_model
        reference_id: str = config.get("tts_custom_voice_id") or config.get("tts_voice_id") or ""
        language: str = config.get("tts_language") or ""
        custom_endpoint: str = config.get("tts_custom_endpoint") or ""

        logger.info(
            "[FISH_AUDIO] TTS  model=%s  reference_id=%s  language=%s  endpoint=%s",
            model, mask(reference_id), language, custom_endpoint or "(default)",
        )
        return FishAudioTTS(
            api_key=api_key,
            model=model,
            reference_id=reference_id,
            language=language,
            custom_endpoint=custom_endpoint,
        )


# ── LiveKit-compatible Fish Audio TTS adapter ────────────────────────

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
        model: str = "",
        reference_id: str = "",
        language: str = "",
        custom_endpoint: str = "",
    ) -> None:
        from app.shared.config.knobs import knobs
        model = model or knobs.fish_audio_tts.default_model
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=knobs.fish_audio_tts.sample_rate,
            num_channels=knobs.fish_audio_tts.num_channels,
        )
        self._api_key = api_key
        self._model = model
        self._reference_id = reference_id
        self._language = language
        self._custom_endpoint = custom_endpoint
        self._session = None  # lazily created aiohttp session
        self._handlers: dict = {}  # per-instance event handler registry (NOT class-level)

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

    def on(self, event: str, callback=None):
        if callback is None:
            def decorator(fn):
                self._handlers.setdefault(event, []).append(fn)
                return fn
            return decorator
        self._handlers.setdefault(event, []).append(callback)
        return callback

    def emit(self, event: str, *args, **kwargs):
        for handler in self._handlers.get(event, []):
            try:
                handler(*args, **kwargs)
            except Exception:
                pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type=None, exc=None, exc_tb=None):
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
        self._fish_tts: FishAudioTTS = tts
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
            session = self._fish_tts._ensure_session()

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
                "[FISH_AUDIO] synthesize  model=%s  text_len=%d  endpoint=%s",
                self._model, len(self._input_text), self._custom_endpoint or "(default)",
            )

            from app.shared.config.knobs import knobs
            timeout_sec = self._conn_options.timeout if self._conn_options else knobs.fish_audio_tts.connect_timeout_seconds
            total_timeout_sec = knobs.fish_audio_tts.total_timeout_seconds
            api_url = self._custom_endpoint.rstrip("/") + "/v1/tts" if self._custom_endpoint else f"{FISH_AUDIO_API_URL}/v1/tts"
            async with session.post(
                api_url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=total_timeout_sec, sock_connect=timeout_sec),
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
