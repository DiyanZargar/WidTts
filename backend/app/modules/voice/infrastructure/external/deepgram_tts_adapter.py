import json
import asyncio
from typing import Optional, AsyncGenerator
import httpx
from deepgram import AsyncDeepgramClient
from deepgram.core.events import EventType
from deepgram.speak.v1.types import SpeakV1Text
from deepgram.speak.v2.types import SpeakV2Speak
from app.shared.config.settings import settings
from app.shared.logging.logger import logger
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface


class DeepgramTTSAdapter(TTSProviderInterface):
    """
    Deepgram TTS adapter using official SDK (deepgram-sdk v7.x).

    Supports both v1 (Aura/Aura-2 models) and v2 (Flux models like flux-alexis-en).

    Follows the official template pattern:
        1. connect_stream()  – opens persistent WebSocket via async context manager
        2. register event handlers (MESSAGE, OPEN, CLOSE, ERROR)
        3. start_listening() – background async for loop over websocket
        4. synthesize_stream(text) – sends text, yields audio chunks as they arrive
        5. close() – exits context manager, shuts down WebSocket and REST client
    """

    def __init__(self):
        self._client: Optional[AsyncDeepgramClient] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        self._ctx = None           # async context manager handle
        self._conn = None          # AsyncV1SocketClient or AsyncV2SocketClient
        self._tts_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self._stream_connected: bool = False
        self._listen_task: Optional[asyncio.Task] = None
        self._closed: bool = False
        self._is_v2: bool = False

    @staticmethod
    def _is_v2_model(model_name: str) -> bool:
        m = model_name.lower().strip()
        return m.startswith("flux-") or "v2" in m

    # ── REST fallback (backward compatible) ──

    def _get_http_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=10.0,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._http_client

    async def synthesize(self, text: str) -> bytes:
        model_name = settings.deepgram_tts_model
        version = "v2" if self._is_v2_model(model_name) else "v1"
        tts_url = f"https://api.deepgram.com/{version}/speak?model={model_name}"
        client = self._get_http_client()
        resp = await client.post(
            tts_url,
            headers={
                "Authorization": f"Token {settings.deepgram_api_key}",
                "Content-Type": "application/json",
            },
            json={"text": text},
        )
        resp.raise_for_status()
        return resp.content

    # ── Streaming WebSocket ──

    def _on_message(self, message) -> None:
        """
        Callback for all WebSocket messages from Deepgram.
        - bytes → audio chunk (enqueue immediately)
        - Flushed / Cleared → end-of-stream sentinel
        - Warning / Error / Metadata → log
        """
        if isinstance(message, bytes):
            try:
                self._tts_queue.put_nowait(message)
                logger.debug(f"[TTS MSG] Enqueued audio chunk ({len(message)} bytes)")
            except asyncio.QueueFull:
                logger.warning("[TTS MSG] Queue full — dropping audio chunk")
            return

        # SDK v7 passes typed Pydantic model objects — check .type attribute first
        msg_type = getattr(message, "type", None)
        if msg_type is None and isinstance(message, dict):
            msg_type = message.get("type", "")
        if msg_type is None:
            try:
                data = json.loads(message)
                if isinstance(data, dict):
                    msg_type = data.get("type", "")
            except (json.JSONDecodeError, TypeError):
                pass

        logger.info(f"[TTS MSG] Received control message type={msg_type}")

        is_eos = False
        if getattr(self, "_is_v2", False):
            # In v2 (Flux), 'Flushed' arrives BEFORE audio bytes. 'SpeechMetadata' marks completion.
            if msg_type in ("SpeechMetadata", "SpeakV2SpeechMetadata", "Cleared", "SpeakV2Cleared"):
                is_eos = True
        else:
            # In v1 (Aura), 'Flushed' arrives AFTER audio bytes.
            if msg_type in ("Flushed", "Cleared"):
                is_eos = True

        if is_eos:
            try:
                self._tts_queue.put_nowait(None)  # end-of-stream sentinel
                logger.info(f"[TTS MSG] Enqueued EOS sentinel ({msg_type})")
            except asyncio.QueueFull:
                logger.warning(f"[TTS MSG] Queue full — dropping {msg_type} sentinel")
        elif msg_type in ("Warning", "Error", "SpeakV2Warning", "SpeakV2Error"):
            logger.warning(f"[TTS MSG] Warning/Error: {message}")
        elif msg_type in ("Metadata", "SpeakV2SessionMetadata", "SpeakV2SpeechMetadata", "Flushed", "SpeakV2Flushed"):
            logger.info(f"[TTS MSG] Control message: {msg_type}")

    def _on_close(self) -> None:
        logger.info("[TTS CONNECT] Deepgram TTS WebSocket closed by server")
        self._stream_connected = False

    def _drain_queue(self) -> None:
        while not self._tts_queue.empty():
            try:
                self._tts_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def _cleanup_connection(self) -> None:
        """Cancel listener and close websocket without raising."""
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._conn and self._ctx:
            try:
                await self._conn.send_close()
            except Exception:
                pass
            try:
                await self._ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._conn = None
            self._ctx = None

        self._stream_connected = False

    async def connect_stream(self) -> None:
        """
        Open persistent WebSocket. Idempotent — reconnects if the listener died.
        """
        if self._stream_connected and self._listen_task and not self._listen_task.done():
            return

        # If previously connected but listener died, clean up first
        if self._stream_connected or self._conn:
            await self._cleanup_connection()

        self._client = AsyncDeepgramClient(api_key=settings.deepgram_api_key)
        self._drain_queue()
        self._closed = False

        model_name = settings.deepgram_tts_model
        self._is_v2 = self._is_v2_model(model_name)

        if self._is_v2:
            self._ctx = self._client.speak.v2.connect(
                model=model_name,
                encoding="linear16",
                sample_rate="48000",
            )
        else:
            self._ctx = self._client.speak.v1.connect(
                model=model_name,
                encoding="linear16",
                sample_rate="48000",
            )

        self._conn = await self._ctx.__aenter__()

        # Register event handlers BEFORE start_listening (template pattern)
        self._conn.on(EventType.MESSAGE, self._on_message)
        self._conn.on(EventType.OPEN, lambda _: logger.info(
            f"[TTS CONNECT] Deepgram TTS WebSocket opened (model={model_name}, version={'v2' if self._is_v2 else 'v1'})"))
        self._conn.on(EventType.CLOSE, lambda _: self._on_close())
        self._conn.on(EventType.ERROR, lambda error: logger.error(
            f"[TTS CONNECT] Error: {error}"))

        # start_listening() enters an infinite async for loop — run as background task
        self._listen_task = asyncio.create_task(self._conn.start_listening())
        self._stream_connected = True
        logger.info(f"[TTS CONNECT] Deepgram TTS WebSocket connected (model={model_name}, version={'v2' if self._is_v2 else 'v1'})")

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Send text to Deepgram and yield audio chunks as they arrive.
        Uses a 30-second timeout per chunk to prevent indefinite blocking
        if the connection drops silently.
        """
        if not self._stream_connected or not self._conn or (self._listen_task and self._listen_task.done()):
            await self.connect_stream()
        self._drain_queue()

        if getattr(self, "_is_v2", False):
            await self._conn.send_speak(SpeakV2Speak(text=text))
            await self._conn.send_flush()
        else:
            await self._conn.send_text(SpeakV1Text(text=text))
            await self._conn.send_flush()
        logger.info(f"[TTS STREAM] Sent text ({len(text)} chars) + flush. Yielding chunks...")

        chunk_count = 0
        while True:
            try:
                chunk = await asyncio.wait_for(self._tts_queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                logger.error(
                    "[TTS STREAM] Timeout: no audio chunk from Deepgram for 30s. "
                    "The connection may have dropped silently."
                )
                self._stream_connected = False
                raise RuntimeError(
                    "TTS streaming timeout — Deepgram did not send audio within 30s"
                )

            if chunk is None:
                logger.info(f"[TTS STREAM] Stream complete — received {chunk_count} chunks")
                break

            chunk_count += 1
            yield chunk

    async def close(self) -> None:
        """Clean shutdown — cancel listener, close websocket, drain queue."""
        self._closed = True
        await self._cleanup_connection()
        self._drain_queue()

        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

        self._client = None
        logger.info("[TTS CLOSE] Deepgram TTS adapter closed cleanly.")
