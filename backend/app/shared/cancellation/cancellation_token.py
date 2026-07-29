"""
CancellationToken — unified cancellation framework.

A single token propagates cancellation to STT, LLM, TTS, playback,
pending tasks, streaming pipelines, and event listeners.

Cancellation is idempotent and safe to call multiple times.
"""
import asyncio
from typing import Callable, Set, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("cancellation")


@dataclass
class CancellationToken:
    """Lightweight cooperative cancellation token."""

    _cancelled: bool = field(default=False, init=False)
    _reason: str = field(default="", init=False)
    _callbacks: Set[Callable[[], None]] = field(default_factory=set, init=False)
    _async_callbacks: Set[Callable[[], asyncio.coroutine]] = field(default_factory=set, init=False)
    _event: asyncio.Event = field(default_factory=asyncio.Event, init=False)

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled

    @property
    def reason(self) -> str:
        return self._reason

    def cancel(self, reason: str = "cancelled") -> None:
        """Cancel this token. Idempotent — safe to call multiple times."""
        if self._cancelled:
            return
        self._cancelled = True
        self._reason = reason
        self._event.set()
        logger.info(f"[CANCEL] Token cancelled: reason='{reason}'")

        for cb in list(self._callbacks):
            try:
                cb()
            except Exception:
                logger.exception("[CANCEL] Sync callback error")

        for cb in list(self._async_callbacks):
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.ensure_future(cb())
                else:
                    loop.run_until_complete(cb())
            except Exception:
                logger.exception("[CANCEL] Async callback error")

    def on_cancel(self, callback: Callable[[], None]) -> None:
        """Register a synchronous callback for cancellation."""
        if self._cancelled:
            try:
                callback()
            except Exception:
                pass
        else:
            self._callbacks.add(callback)

    def on_cancel_async(self, callback) -> None:
        """Register an async callback for cancellation."""
        if self._cancelled:
            asyncio.ensure_future(callback())
        else:
            self._async_callbacks.add(callback)

    def remove_callback(self, callback) -> None:
        self._callbacks.discard(callback)
        self._async_callbacks.discard(callback)

    async def wait(self, timeout: Optional[float] = None) -> bool:
        """Wait for cancellation. Returns True if cancelled, False on timeout."""
        try:
            await asyncio.wait_for(self._event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def check(self) -> None:
        """Raise CancelledError if this token has been cancelled."""
        if self._cancelled:
            raise asyncio.CancelledError(f"CancellationToken: {self._reason}")

    def child(self) -> "CancellationToken":
        """Create a child token that is cancelled when the parent is."""
        child_token = CancellationToken()
        self.on_cancel(lambda: child_token.cancel(self._reason))
        return child_token


class CancellationTokenSource:
    """Factory for creating and managing CancellationToken instances."""

    def __init__(self):
        self._token = CancellationToken()

    @property
    def token(self) -> CancellationToken:
        return self._token

    def cancel(self, reason: str = "cancelled") -> None:
        self._token.cancel(reason)

    def create_child(self) -> CancellationToken:
        return self._token.child()
