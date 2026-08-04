"""
ElevenLabs STT adapter using the official WebSocket protocol.

Reference: https://elevenlabs.io/docs/api-reference/speech-to-text/streaming

Protocol:
- Connect to wss://api.elevenlabs.io/v1/speech-to-text/ws
- Auth via xi-api-key header
- Send input_audio messages (base64-encoded PCM)
- Receive session_started, partial_transcript, final_transcript, committed_transcript
"""

import json
import base64
import asyncio
import websockets
from typing import Optional, Dict, Any
from app.shared.logging.logger import logger
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface


class ElevenLabsSTTAdapter(STTProviderInterface):
    """
    ElevenLabs real-time speech-to-text via WebSocket.
    Credentials and model are injected at construction.
    """

    BASE_URL = "wss://api.elevenlabs.io/v1/speech-to-text/ws"

    def __init__(self, api_key: str, model_id: str = "scribe_v1", language: str = "en"):
        self._api_key = api_key
        self._model_id = model_id
        self._language = language
        self._ws = None
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._reader_task: Optional[asyncio.Task] = None
        self._epoch: int = 0
        self._consecutive_errors: int = 0

    async def _listen_loop(self) -> None:
        """Background listener for ElevenLabs STT WebSocket messages."""
        logger.info("[EL-STT LISTENER] Background listener starting.")
        while self._ws:
            try:
                message = await self._ws.recv()
            except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
                logger.info("[EL-STT LISTENER] WebSocket closed — listener exiting.")
                break
            except Exception as e:
                self._consecutive_errors += 1
                sleep_time = 2.0 if self._consecutive_errors >= 10 else 0.5
                logger.error(
                    f"[EL-STT READER ERROR] Exception (consecutive={self._consecutive_errors}): {e}"
                )
                await asyncio.sleep(sleep_time)
                continue

            self._consecutive_errors = 0

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                logger.warning(f"[EL-STT] Non-JSON message: {str(message)[:100]}")
                continue

            msg_type = data.get("type", data.get("message_type", "unknown"))

            # Log relevant messages
            if msg_type in ("partial_transcript", "final_transcript", "committed_transcript"):
                text = data.get("text", "")
                logger.info(
                    f"[EL-STT RECEIVED] {msg_type}: '{text[:60]}' | epoch={self._epoch}"
                )
            elif msg_type == "session_started":
                logger.info(f"[EL-STT] Session started: {data.get('session_id', 'unknown')}")
            elif msg_type == "error":
                logger.error(f"[EL-STT ERROR] {data.get('message', data)}")
            else:
                logger.debug(f"[EL-STT] type={msg_type}")

            item = {"epoch": self._epoch, "data": data}

            if self._queue.full():
                try:
                    self._queue.get_nowait()
                    logger.warning("[EL-STT QUEUE OVERFLOW] Discarded oldest item.")
                except asyncio.QueueEmpty:
                    pass

            await self._queue.put(item)
        logger.info("[EL-STT LISTENER] Listener task finished.")

    def _start_reader(self) -> None:
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
        self._reader_task = asyncio.create_task(self._listen_loop())

    async def connect(self) -> None:
        """Connect to ElevenLabs STT WebSocket."""
        url = f"{self.BASE_URL}?model_id={self._model_id}&language_code={self._language}"

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
        self._consecutive_errors = 0
        self._start_reader()
        logger.info("[EL-STT CONNECT] ElevenLabs STT WebSocket connected.")

    def _drain_queue(self) -> None:
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def send_audio(self, chunk: bytes) -> None:
        """Send audio chunk as base64-encoded input_audio message."""
        if not self._ws or (self._reader_task and self._reader_task.done()):
            logger.warning("[EL-STT RECONNECT] Reconnecting...")
            try:
                await self.connect()
            except Exception as e:
                logger.error(f"[EL-STT RECONNECT ERROR] {e}")
                return

        audio_b64 = base64.b64encode(chunk).decode("utf-8")
        msg = json.dumps({
            "type": "input_audio",
            "audio": audio_b64,
        })

        try:
            await self._ws.send(msg)
        except (websockets.exceptions.ConnectionClosed, AttributeError):
            try:
                await self.connect()
                await self._ws.send(msg)
            except Exception as e:
                logger.error(f"[EL-STT SEND ERROR] {e}")

    def advance_epoch(self) -> int:
        self._epoch += 1
        logger.info(f"[EL-STT EPOCH] Advanced epoch to {self._epoch}")
        return self._epoch

    async def receive_any(self) -> Dict[str, Any]:
        try:
            item = self._queue.get_nowait()
            data = item.get("data", {})
            data["_epoch"] = item.get("epoch", 0)
            return data
        except asyncio.QueueEmpty:
            return {}

    async def drain_pending(self) -> None:
        self._drain_queue()
        logger.info("[EL-STT DRAIN] Flushed pending STT queue.")

    async def drain_before(self, epoch: int) -> int:
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
                discarded += 1

        if discarded:
            logger.info(f"[EL-STT DRAIN EPOCH] Discarded {discarded} items before epoch={epoch}")
        return discarded

    def parse_stt_message(self, raw: dict) -> tuple:
        """
        Parse ElevenLabs STT message.
        committed_transcript → final=True (same code path as Deepgram final)
        final_transcript → final=True
        partial_transcript → final=False
        """
        msg_type = raw.get("type", raw.get("message_type", ""))
        text = raw.get("text", "")

        is_final = msg_type in ("committed_transcript", "final_transcript")
        return text.strip(), is_final

    async def receive_transcript(self) -> Optional[str]:
        data = await self.receive_any()
        text, is_final = self.parse_stt_message(data)
        return text if is_final and text else None

    async def close(self) -> None:
        if self._reader_task and not self._reader_task.done():
            self._reader_task.cancel()
            self._reader_task = None

        if self._ws:
            # Send end_of_audio signal before closing
            try:
                await self._ws.send(json.dumps({"type": "end_of_audio"}))
            except Exception:
                pass
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

        self._drain_queue()
        logger.info("[EL-STT CLOSE] ElevenLabs STT adapter closed cleanly.")
