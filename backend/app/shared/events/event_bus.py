import asyncio
import logging
from typing import Any, Callable, Dict, List
from dataclasses import dataclass

logger = logging.getLogger("event_bus")


@dataclass(frozen=True)
class Event:
    name: str
    payload: Any
    session_id: str = ""


class EventBus:
    """Internal async event dispatcher — no external infrastructure required."""

    def __init__(self):
        self._handlers: Dict[str, List[Callable[[Event], Any]]] = {}
        self._async_handlers: Dict[str, List[Callable[[Event], Any]]] = {}

    def subscribe(self, event_name: str, handler: Callable[[Event], Any]) -> None:
        self._handlers.setdefault(event_name, []).append(handler)

    def subscribe_async(self, event_name: str, handler: Callable[[Event], Any]) -> None:
        self._async_handlers.setdefault(event_name, []).append(handler)

    def unsubscribe(self, event_name: str, handler) -> None:
        if event_name in self._handlers:
            self._handlers[event_name] = [h for h in self._handlers[event_name] if h is not handler]
        if event_name in self._async_handlers:
            self._async_handlers[event_name] = [h for h in self._async_handlers[event_name] if h is not handler]

    async def publish(self, event: Event) -> None:
        for handler in self._handlers.get(event.name, []):
            try:
                handler(event)
            except Exception:
                logger.exception(f"[EVENT_BUS] Sync handler error for {event.name}")
        for handler in self._async_handlers.get(event.name, []):
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception(f"[EVENT_BUS] Async handler error for {event.name}")

    async def publish_raw(self, name: str, payload: Any, session_id: str = "") -> None:
        await self.publish(Event(name=name, payload=payload, session_id=session_id))
