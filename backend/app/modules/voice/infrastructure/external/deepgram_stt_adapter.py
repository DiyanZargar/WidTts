import json
import time
import asyncio
import websockets
from typing import Optional, Dict, Any
from app.shared.config.settings import settings
from app.shared.logging.logger import logger
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface


class DeepgramSTTAdapter(STTProviderInterface):
    """
    Deepgram STT adapter using raw websockets (not the SDK).

    The SDK's listen.v1.connect() obscures connection state and silently
    drops messages when the connection is half-open. Raw websockets give
    us direct control over send/recv, timeout-based dead connection
    detection, and immediate error visibility.
    """

    def __init__(self):
        self._ws = None
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._reader_task: Optional[asyncio.Task] = None
        self._epoch: int = 0
        self._consecutive_errors: int = 0
        self._header_chunk: Optional[bytes] = None

    async def _listen_loop(self) -> None:
        """Continuous background listener task for Deepgram WebSocket frames."""
        logger.info("[STT LISTENER] Background listener task starting.")
        while self._ws:
            try:
                message = await self._ws.recv()
            except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
                logger.info("[STT LISTENER] WebSocket closed — listener exiting.")
                break
            except Exception as e:
                self._consecutive_errors += 1
                if self._consecutive_errors >= 10:
                    sleep_time = 2.0
                else:
                    sleep_time = 0.5
                logger.error(
                    f"[STT READER ERROR] Exception in Deepgram WebSocket reader "
                    f"(consecutive={self._consecutive_errors}): {e}"
                )
                await asyncio.sleep(sleep_time)
                continue

            # Successful recv — reset error counter and process message
            self._consecutive_errors = 0
            data = json.loads(message)

            # Log ALL received messages for debugging (not just transcripts)
            msg_type = data.get("type", "unknown")
            channel = data.get("channel") if isinstance(data.get("channel"), dict) else {}
            alt = channel.get("alternatives", [{}])[0] if channel else {}
            text = alt.get("transcript", "")
            is_final = data.get("is_final", False)
            if text:
                logger.info(
                    f"[STT RECEIVED] {'FINAL' if is_final else 'PARTIAL'} transcript: "
                    f"'{text[:60]}' | epoch={self._epoch}"
                )
            else:
                logger.info(f"[STT RECEIVED] type={msg_type} (no transcript)")

            item = {"epoch": self._epoch, "data": data}

            # If queue is full, discard oldest item to make room
            if self._queue.full():
                try:
                    self._queue.get_nowait()
                    logger.warning("[STT QUEUE OVERFLOW] Queue full — discarded oldest item.")
                except asyncio.QueueEmpty:
                    pass

            await self._queue.put(item)
        logger.info("[STT LISTENER] Listener task finished.")

    def _start_reader(self) -> None:
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
        self._reader_task = asyncio.create_task(self._listen_loop())

    async def connect(self) -> None:
        headers = {"Authorization": f"Token {settings.deepgram_api_key}"}
        try:
            self._ws = await websockets.connect(
                settings.deepgram_stt_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
            )
        except TypeError:
            self._ws = await websockets.connect(
                settings.deepgram_stt_url,
                extra_headers=headers,
                ping_interval=20,
                ping_timeout=20,
            )

        self._drain_queue()
        self._consecutive_errors = 0
        self._start_reader()
        logger.info("[STT CONNECT] Deepgram WebSocket connected and background reader started.")

        # Re-send cached WebM header chunk if reconnecting mid-session
        if self._header_chunk is not None:
            try:
                await self._ws.send(self._header_chunk)
                logger.info("[STT CONNECT] Sent cached WebM header chunk to new WebSocket.")
            except Exception as e:
                logger.error(f"[STT CONNECT] Failed to send cached header chunk: {e}")

    def _drain_queue(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def send_audio(self, chunk: bytes) -> None:
        # Cache first chunk (WebM header) for session reconnects
        if self._header_chunk is None:
            self._header_chunk = chunk

        if not self._ws or (self._reader_task and self._reader_task.done()):
            logger.warning(
                f"[STT RECONNECT] ws={'alive' if self._ws else 'None'} "
                f"reader={'done' if (self._reader_task and self._reader_task.done()) else 'running' if self._reader_task else 'None'} "
                f"— reconnecting"
            )
            await self.connect()

        _t0 = time.monotonic()
        try:
            await self._ws.send(chunk)
            _ms = int((time.monotonic() - _t0) * 1000)
            if _ms > 50:
                logger.warning(f"[STT SEND SLOW] send_audio took {_ms}ms for {len(chunk)} bytes")
        except (websockets.exceptions.ConnectionClosed, AttributeError):
            try:
                await self.connect()
                await self._ws.send(chunk)
            except Exception as e:
                logger.error(f"[STT SEND ERROR] Failed to send audio chunk to Deepgram: {e}")

    def advance_epoch(self) -> int:
        """Increment the epoch counter and return the new value."""
        self._epoch += 1
        logger.info(f"[STT EPOCH] Advanced epoch to {self._epoch}")
        return self._epoch

    async def receive_any(self) -> Dict[str, Any]:
        """Fetch next parsed message from internal queue (non-blocking)."""
        try:
            item = self._queue.get_nowait()
            data = item.get("data", {})
            data["_epoch"] = item.get("epoch", 0)
            return data
        except asyncio.QueueEmpty:
            return {}

    async def drain_pending(self) -> None:
        """Instantly flush all pending STT messages in queue."""
        self._drain_queue()
        logger.info("[STT DRAIN] Instantly flushed pending STT queue.")

    async def drain_before(self, epoch: int) -> int:
        """Drain only items older than the given epoch, keeping current items."""
        kept = []
        discarded = 0
        while not self._queue.empty():
            try:
                item = self._queue.get_nowait()
                if item.get("epoch", 0) < epoch:
                    discarded += 1
                else:
                    kept.append(item)
            except asyncio.QueueEmpty:
                break

        for item in kept:
            try:
                self._queue.put_nowait(item)
            except asyncio.QueueFull:
                logger.warning("[STT DRAIN] Queue full while re-inserting kept items — discarding.")
                discarded += 1

        if discarded:
            logger.info(f"[STT DRAIN EPOCH] Discarded {discarded} items before epoch={epoch}")
        return discarded

    async def receive_transcript(self) -> Optional[str]:
        data = await self.receive_any()
        channel = data.get("channel") if isinstance(data.get("channel"), dict) else {}
        alt = channel.get("alternatives", [{}])[0] if channel else {}
        transcript = alt.get("transcript", "")
        return transcript if data.get("is_final") and transcript else None

    async def close(self) -> None:
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            self._reader_task = None

        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        self._header_chunk = None
        self._drain_queue()
        logger.info("[STT CLOSE] Deepgram STT adapter closed cleanly.")
