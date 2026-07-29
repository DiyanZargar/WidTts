from typing import Dict, Any, Callable, Awaitable
import logging

logger = logging.getLogger("task_router")


class TaskRouter:
    """
    Maps intent classifications to handler functions.

    Responsibilities:
    - Register handlers for each intent type
    - Route classified intents to the correct handler
    - Provide default/fallback behavior for unknown intents

    Separated from Intent Detector — detection says WHAT, routing says HOW.
    """

    def __init__(self):
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {}
        self._fallback: Callable[[Dict[str, Any]], Awaitable[Any]] = self._default_fallback

    def register(
        self,
        intent_type: str,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]],
    ) -> None:
        """Register a handler for a specific intent type."""
        self._handlers[intent_type] = handler
        logger.info(f"[TASK_ROUTER] Registered handler for '{intent_type}'")

    def set_fallback(
        self,
        handler: Callable[[Dict[str, Any]], Awaitable[Any]],
    ) -> None:
        """Set the fallback handler for unregistered intent types."""
        self._fallback = handler

    async def route(self, intent_type: str, context: Dict[str, Any]) -> Any:
        """
        Route an intent to its registered handler.

        Args:
            intent_type: The classified intent (e.g. "STOP", "ANSWER", "CORRECTION")
            context: All data needed by handlers (session_id, turn_id, transcript, etc.)

        Returns:
            Handler result, or fallback result if no handler registered.
        """
        handler = self._handlers.get(intent_type)
        if handler is None:
            logger.warning(f"[TASK_ROUTER] No handler for '{intent_type}' — using fallback")
            return await self._fallback(context)

        logger.info(f"[TASK_ROUTER] Routing '{intent_type}' to registered handler")
        return await handler(context)

    @staticmethod
    async def _default_fallback(context: Dict[str, Any]) -> Dict[str, Any]:
        """Default fallback: log and return no-op result."""
        logger.warning(f"[TASK_ROUTER] Fallback triggered for context: {context.keys()}")
        return {"handled": False, "reason": "No handler registered for this intent"}
