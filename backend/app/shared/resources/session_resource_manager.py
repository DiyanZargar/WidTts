"""
Session Resource Manager — deterministic resource lifecycle.

When a session ends, ALL resources are released in one place.
No resource cleanup is distributed across unrelated components.
"""
import asyncio
from typing import Set, Optional, Dict, Any, Callable
import logging

logger = logging.getLogger("session_resources")


class SessionResourceManager:
    """Tracks and releases all runtime resources for a session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._tasks: Set[asyncio.Task] = set()
        self._timers: Set[asyncio.TimerHandle] = set()
        self._cleanup_callbacks: Dict[str, Callable] = {}
        self._audio_context = None
        self._websocket = None
        self._stt_stream = None
        self._tts_stream = None
        self._worklets: list = []
        self._event_subscriptions: list = []
        self._playback_buffers: list = []
        self._released = False

    # ── Registration ──

    def track_task(self, task: asyncio.Task) -> None:
        if self._released:
            task.cancel()
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    def track_timer(self, handle: asyncio.TimerHandle) -> None:
        self._timers.add(handle)

    def register_resource(self, name: str, resource: Any, cleanup: Optional[Callable] = None) -> None:
        setattr(self, f"_res_{name}", resource)
        if cleanup:
            self._cleanup_callbacks[name] = cleanup

    def register_audio_context(self, ctx) -> None:
        self._audio_context = ctx

    def register_websocket(self, ws) -> None:
        self._websocket = ws

    def register_stt_stream(self, stream) -> None:
        self._stt_stream = stream

    def register_tts_stream(self, stream) -> None:
        self._tts_stream = stream

    def register_worklet(self, node) -> None:
        self._worklets.append(node)

    def register_event_subscription(self, unsubscribe_fn: Callable) -> None:
        self._event_subscriptions.append(unsubscribe_fn)

    def register_playback_buffer(self, buffer) -> None:
        self._playback_buffers.append(buffer)

    # ── Release ──

    async def release_all(self) -> None:
        """Deterministically release ALL registered resources."""
        if self._released:
            return
        self._released = True
        released = []

        # Cancel all tasks
        for task in list(self._tasks):
            if not task.done():
                task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()
            released.append(f"tasks")

        # Cancel timers
        for handle in self._timers:
            handle.cancel()
        self._timers.clear()
        if self._timers:
            released.append("timers")

        # Worklets
        for node in self._worklets:
            try:
                node.disconnect()
            except Exception:
                pass
        self._worklets.clear()
        if self._worklets:
            released.append("worklets")

        # Audio context
        if self._audio_context:
            try:
                if self._audio_context.state != "closed":
                    await self._audio_context.close()
            except Exception:
                pass
            self._audio_context = None
            released.append("audio_context")

        # STT stream
        if self._stt_stream:
            try:
                await self._stt_stream.close()
            except Exception:
                pass
            self._stt_stream = None
            released.append("stt_stream")

        # TTS stream
        if self._tts_stream:
            try:
                await self._tts_stream.close()
            except Exception:
                pass
            self._tts_stream = None
            released.append("tts_stream")

        # Event subscriptions
        for unsub in self._event_subscriptions:
            try:
                unsub()
            except Exception:
                pass
        self._event_subscriptions.clear()
        if self._event_subscriptions:
            released.append("event_subscriptions")

        # Playback buffers
        self._playback_buffers.clear()

        # Custom cleanup callbacks
        for name, cleanup_fn in self._cleanup_callbacks.items():
            try:
                result = cleanup_fn()
                if asyncio.iscoroutine(result):
                    await result
                released.append(name)
            except Exception:
                logger.exception(f"[SESSION_RESOURCES] Cleanup error for {name}")

        logger.info(f"[SESSION_RESOURCES] Released session={self.session_id} resources={released}")

    @property
    def is_released(self) -> bool:
        return self._released

    def snapshot(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "released": self._released,
            "active_tasks": len(self._tasks),
            "active_timers": len(self._timers),
            "worklets": len(self._worklets),
            "event_subscriptions": len(self._event_subscriptions),
            "has_audio_context": self._audio_context is not None,
            "has_websocket": self._websocket is not None,
            "has_stt": self._stt_stream is not None,
            "has_tts": self._tts_stream is not None,
        }
