"""
ElevenLabs TTS adapter using the official WebSocket streaming protocol.

Reference: https://elevenlabs.io/docs/api-reference/text-to-speech/streaming

Protocol:
- Connect to wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input
- Auth via xi-api-key header
- Initialize: {"text": " ", "voice_settings": {...}, "xi_api_key": "..."}
- Per sentence: {"text": "<sentence>"}
- Close: {"text": ""}
- Receive: base64-encoded audio chunks with alignment info
"""

import json
import base64
import asyncio
import websockets
from typing import Optional, AsyncGenerator
from app.shared.logging.logger import logger
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface


class ElevenLabsTTSAdapter(TTSProviderInterface):
    """
    ElevenLabs TTS streaming via WebSocket input streaming protocol.
    Credentials, voice_id, and model are injected at construction.
    """

    BASE_URL = "wss://api.elevenlabs.io/v1/text-to-speech"

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model_id: str = "eleven_turbo_v2_5",
        output_format: str = "pcm_24000",
        stability: float = 0.5,
        similarity_boost: float = 0.75,
    ):
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._output_format = output_format
        self._stability = stability
        self._similarity_boost = similarity_boost
        self._ws = None
        self._audio_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._reader_task: Optional[asyncio.Task] = None
        self._stream_connected: bool = False
        self._closed: bool = False

    async def _listen_loop(self) -> None:
        """Background listener for ElevenLabs TTS WebSocket audio responses."""
        logger.info("[EL-TTS LISTENER] Background listener starting.")
        while self._ws:
            try:
                message = await self._ws.recv()
            except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
                logger.info("[EL-TTS LISTENER] WebSocket closed — exiting.")
                break
            except Exception as e:
                logger.error(f"[EL-TTS READER ERROR] {e}")
                await asyncio.sleep(0.5)
                continue

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                # Might be raw binary (unlikely with ElevenLabs)
                if isinstance(message, bytes):
                    try:
                        self._audio_queue.put_nowait(message)
                    except asyncio.QueueFull:
                        logger.warning("[EL-TTS] Queue full — dropping chunk")
                continue

            # Audio data comes as base64 in the "audio" field
            audio_b64 = data.get("audio")
            if audio_b64:
                audio_bytes = base64.b64decode(audio_b64)
                try:
                    self._audio_queue.put_nowait(audio_bytes)
                    logger.debug(f"[EL-TTS MSG] Enqueued audio ({len(audio_bytes)} bytes)")
                except asyncio.QueueFull:
                    logger.warning("[EL-TTS MSG] Queue full — dropping audio chunk")

            # is_final signals end of stream for this text
            if data.get("isFinal", False):
                try:
                    self._audio_queue.put_nowait(None)  # EOS sentinel
                    logger.info("[EL-TTS MSG] Enqueued EOS sentinel (isFinal)")
                except asyncio.QueueFull:
                    logger.warning("[EL-TTS MSG] Queue full — dropping EOS")

            # Handle error messages
            if data.get("error"):
                logger.error(f"[EL-TTS ERROR] {data['error']}")

        logger.info("[EL-TTS LISTENER] Listener finished.")

    def _drain_queue(self) -> None:
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def connect_stream(self) -> None:
        """Open persistent WebSocket for TTS streaming."""
        if self._stream_connected and self._reader_task and not self._reader_task.done():
            return

        if self._stream_connected or self._ws:
            await self._cleanup_connection()

        url = (
            f"{self.BASE_URL}/{self._voice_id}/stream-input"
            f"?model_id={self._model_id}"
            f"&output_format={self._output_format}"
        )

        headers = {"xi-api-key": self._api_key}

        try:
            self._ws = await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
            )
        except TypeError:
            self._ws = await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=20,
            )

        self._drain_queue()
        self._closed = False

        # Start background reader
        self._reader_task = asyncio.create_task(self._listen_loop())

        # Send initialization message (BOS - Beginning of Stream)
        init_msg = json.dumps({
            "text": " ",
            "voice_settings": {
                "stability": self._stability,
                "similarity_boost": self._similarity_boost,
            },
            "xi_api_key": self._api_key,
        })
        await self._ws.send(init_msg)

        self._stream_connected = True
        logger.info(f"[EL-TTS CONNECT] Connected (voice={self._voice_id}, model={self._model_id})")

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """Send text and yield audio chunks as they arrive, with REST fallback on error."""
        try:
            if not self._stream_connected or not self._ws or (self._reader_task and self._reader_task.done()):
                await self.connect_stream()

            self._drain_queue()

            # Send text
            await self._ws.send(json.dumps({"text": text}))

            # Send flush (empty text signals end of this input)
            await self._ws.send(json.dumps({"text": "", "flush": True}))

            logger.info(f"[EL-TTS STREAM] Sent text ({len(text)} chars). Yielding chunks...")

            chunk_count = 0
            while True:
                chunk = await asyncio.wait_for(self._audio_queue.get(), timeout=5.0)
                if chunk is None:
                    logger.info(f"[EL-TTS STREAM] Complete — {chunk_count} chunks")
                    break
                chunk_count += 1
                yield chunk

        except Exception as err:
            logger.warning(f"[EL-TTS STREAM FALLBACK] WebSocket stream failed ({err}) — falling back to REST synthesis")
            self._stream_connected = False
            rest_audio = await self.synthesize(text)
            chunk_size = 4096
            for i in range(0, len(rest_audio), chunk_size):
                yield rest_audio[i:i+chunk_size]

    async def synthesize(self, text: str) -> bytes:
        """HTTP REST synthesis fallback."""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self._voice_id}"
        headers = {
            "xi-api-key": self._api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {
                "stability": self._stability,
                "similarity_boost": self._similarity_boost,
            },
        }
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            return resp.content

    async def _cleanup_connection(self) -> None:
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

        if self._ws:
            try:
                # Send EOS (End of Stream) — empty text
                await self._ws.send(json.dumps({"text": ""}))
            except Exception:
                pass
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        self._stream_connected = False

    async def close(self) -> None:
        self._closed = True
        await self._cleanup_connection()
        self._drain_queue()
        logger.info("[EL-TTS CLOSE] ElevenLabs TTS adapter closed cleanly.")
