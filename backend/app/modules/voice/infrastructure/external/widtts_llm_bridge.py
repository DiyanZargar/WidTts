"""
WidTTS LLM Bridge — the single seam between LiveKit Agents and widTTS
business logic.

This is the **only** custom LiveKit plugin widTTS authors.  It implements
``livekit.agents.llm.LLM`` so it can be passed directly to
``AgentSession(llm=...)``.  All LLM calls flow through the existing
widTTS conversation infrastructure — no livekit-plugins-* LLM backends
are ever imported.

Architecture
------------
LiveKit VoicePipelineAgent
    └─ AgentSession(llm=WidTTSLLMBridge)
        └─ WidTTSLLMBridge.chat(chat_ctx=...)
            ├─ ConversationPolicy.resolve_action()   ← intent classification
            ├─ pre-formed responses for STOP/REPEAT/CORRECTION/END
            └─ ConversationAdapter.stream_chat()      ← streaming LLM for normal answers
                └─ AsyncOpenAI.chat.completions.create(stream=True)

Responsibilities
----------------
1. Extract the committed user transcript from ``ChatContext``.
2. Route through ``ConversationPolicy`` for deterministic command detection
   (stop, repeat, correction, end) before hitting the LLM.
3. For policy actions: yield a single ``ChatChunk`` with the pre-formed
   acknowledgement text.
4. For normal answers (ANSWER / NONE / CONTINUE): delegate to the
   injected ``conversation_adapter`` which streams tokens from the LLM,
   and yield each token as a ``ChatChunk``.

Design constraints
------------------
- **Never** imports ``livekit.plugins.deepgram`` or
  ``livekit.plugins.elevenlabs`` — speech plugins are handled elsewhere.
- The bot's ``system_prompt`` drives the conversation; the bridge is a
  transparent pass-through for LLM generation.
- Structured logging throughout for observability.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable

from livekit.agents.llm import ChatChunk, ChoiceDelta, LLM, LLMStream
from livekit.agents.llm.chat_context import ChatContext
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, APIConnectOptions, NotGivenOr

from app.modules.conversation.domain.policy.conversation_policy import (
    ConversationPolicy,
    PolicyAction,
)

logger = logging.getLogger("widtts_llm_bridge")

from app.shared.logging import pipeline_logger as pl


# ── Conversation Adapter Protocol ────────────────────────────────────

@runtime_checkable
class ConversationAdapterProtocol(Protocol):
    """
    Minimal interface the bridge needs from the conversation adapter.

    The adapter wraps the project's LLM client (``AsyncOpenAI``) and
    yields streaming text tokens.  It is responsible for
    building the messages array (system prompt + context + user message)
    and calling the LLM.

    Uses ``litellm.acompletion()`` to stream chat completions.
    """

    async def stream_chat(
        self,
        *,
        user_text: str,
        system_prompt: str,
        context: List[Dict[str, str]],
        llm_config: Dict[str, Any],
    ) -> AsyncIterator[str]:
        """Stream LLM response tokens for the given user message.

        Parameters
        ----------
        user_text:
            The committed user transcript.
        system_prompt:
            The bot's system prompt that drives the conversation.
        context:
            Recent conversation history as ``[{"role": ..., "content": ...}]``.
        llm_config:
            LLM provider config with ``api_key``, ``base_url``, ``model``.

        Yields
        ------
        str
            Incremental text tokens from the LLM.

        Implementations should be ``async def`` generators that ``yield``
        individual tokens.  Example::

            async def stream_chat(self, *, user_text, system_prompt,
                                  context, llm_config):
                response = await client.chat.completions.create(
                    model=llm_config["model"],
                    messages=_build_messages(system_prompt, context, user_text),
                    stream=True,
                )
                async for chunk in response:
                    token = chunk.choices[0].delta.content
                    if token:
                        yield token
        """
        ...  # pragma: no cover
        # Make this an async generator for type-checking purposes
        yield ""  # noqa: unreachable


# ── Default Conversation Adapter ─────────────────────────────────────

class DefaultConversationAdapter:
    """
    Default implementation of :class:`ConversationAdapterProtocol`.

    Uses ``litellm.acompletion()`` to stream chat completions, supporting
    100+ LLM providers via the model string (e.g. ``gpt-4o``,
    ``gemini/gemini-2.0-flash``, ``anthropic/claude-3-5-sonnet``,
    ``deepseek/deepseek-chat``).  Provider routing is handled entirely
    by litellm — no provider-specific code here.

    Parameters
    ----------
    llm_config:
        LLM provider config with ``api_key``, ``base_url``, ``model``.
    """

    def __init__(self, llm_config: Dict[str, Any]) -> None:
        self._model = llm_config.get("model", "gpt-4o-mini")
        self._api_key = llm_config.get("api_key", "")
        self._base_url = llm_config.get("base_url") or None
        logger.info(
            "[ADAPTER] DefaultConversationAdapter initialized: model=%s base_url=%s",
            self._model,
            self._base_url or "(litellm default)",
        )

    async def stream_chat(
        self,
        *,
        user_text: str,
        system_prompt: str,
        context: List[Dict[str, str]],
        llm_config: Dict[str, Any],
    ) -> AsyncIterator[str]:
        """Stream LLM response tokens via litellm."""
        import litellm

        messages: List[Dict[str, str]] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        for msg in context:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        # Append user_text only if it isn't already present at the end of context
        if not messages or messages[-1].get("content") != user_text:
            messages.append({"role": "user", "content": user_text})

        model = llm_config.get("model") or self._model
        api_key = llm_config.get("api_key") or self._api_key or None
        base_url = llm_config.get("base_url") or self._base_url or None

        # When using a custom endpoint (proxy), litellm always needs "openai/"
        # prefix to route via OpenAI-compatible transport to the api_base URL.
        if base_url and not model.startswith("openai/"):
            model = f"openai/{model}"

        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "stream": True,
            }
            if api_key:
                kwargs["api_key"] = api_key
            if base_url:
                kwargs["api_base"] = base_url

            response = await litellm.acompletion(**kwargs)

            async for chunk in response:
                delta = chunk.choices[0].delta
                token = getattr(delta, "content", None)
                if token:
                    yield token

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("[ADAPTER] LLM stream error: %s", e, exc_info=True)
            yield "I'm sorry, I had trouble generating a response. Could you try again?"


# ── Policy response constants ────────────────────────────────────────

_STOP_ACK = "Alright, I'll pause here. Just say 'continue' when you're ready."
_END_ACK = "Thanks for chatting! Goodbye."
_REPEAT_FALLBACK = "I don't have a previous response to repeat."
_ERROR_ACK = "I'm sorry, something went wrong. Could you try again?"


# ── LLMStream subclass ──────────────────────────────────────────────

class WidTTSLLMStream(LLMStream):
    """
    Concrete ``LLMStream`` that routes through widTTS business logic.

    Created by ``WidTTSLLMBridge.chat()``.  The ``_run()`` method is the
    heart of the bridge — it extracts the transcript, runs policy
    classification, and either yields a pre-formed response or streams
    from the conversation adapter.
    """

    def __init__(
        self,
        bridge: WidTTSLLMBridge,
        *,
        chat_ctx: ChatContext,
        tools: list,
        conn_options: APIConnectOptions,
    ) -> None:
        super().__init__(bridge, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)
        self._bridge = bridge

    async def _run(self) -> None:
        """Execute the bridge logic: extract → classify → respond."""
        t0 = time.monotonic()

        # 1. Extract user text from the committed chat context
        chat_ctx = self._chat_ctx
        user_text = _extract_user_text(chat_ctx)
        if not user_text:
            logger.warning("[BRIDGE] Empty user text in chat context — skipping")
            return

        logger.info(
            "[BRIDGE] Processing user text: %s (len=%d)",
            user_text[:120],
            len(user_text),
        )
        pl.llm_started(session_id="", turn_id="")

        # 2. Route through conversation policy for intent classification
        classification = "ANSWER"  # Default: treat as normal answer
        policy_result = self._bridge._policy.resolve_action(
            classification_type=classification,
            transcript=user_text,
            current_retry_count=0,
        )
        action = policy_result.get("action", PolicyAction.NONE)
        reason = policy_result.get("reason", "")

        logger.info(
            "[BRIDGE] Policy action=%s reason=%s text=%s",
            action.value,
            reason,
            user_text[:80],
        )

        # 3. Handle policy actions with pre-formed responses
        response_text: Optional[str] = None

        if action == PolicyAction.STOP:
            response_text = _STOP_ACK

        elif action == PolicyAction.END_CONVERSATION:
            response_text = _END_ACK

        elif action == PolicyAction.REPEAT:
            response_text = _find_last_assistant_message(chat_ctx) or _REPEAT_FALLBACK

        elif action in (PolicyAction.CORRECTION, PolicyAction.FORGET):
            response_text = None  # Let the LLM handle corrections naturally

        # 4. Emit pre-formed response if we have one (policy shortcut)
        if response_text is not None:
            chunk_id = f"wttp-{uuid.uuid4().hex[:12]}"
            await self._event_ch.send(ChatChunk(
                id=chunk_id,
                delta=ChoiceDelta(role="assistant", content=response_text),
            ))
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.info(
                "[BRIDGE] Policy response action=%s duration_ms=%d text=%s",
                action.value,
                duration_ms,
                response_text[:80],
            )
            return

        # 5. Normal answer / correction / continue — delegate to adapter
        try:
            context_messages = _build_context_messages(chat_ctx)
            token_count = 0
            first_token_time: Optional[float] = None

            async for token in self._bridge._adapter.stream_chat(
                user_text=user_text,
                system_prompt=self._bridge._system_prompt,
                context=context_messages,
                llm_config=self._bridge._llm_config,
            ):
                if not token:
                    continue

                if first_token_time is None:
                    first_token_time = time.monotonic()
                    ttft_ms = int((first_token_time - t0) * 1000)
                    logger.info("[BRIDGE] First token in %dms", ttft_ms)

                token_count += 1
                chunk_id = f"wttp-{uuid.uuid4().hex[:12]}"
                await self._event_ch.send(ChatChunk(
                    id=chunk_id,
                    delta=ChoiceDelta(role="assistant", content=token),
                ))

            duration_ms = int((time.monotonic() - t0) * 1000)
            ttft_ms = int((first_token_time - t0) * 1000) if first_token_time else -1
            logger.info(
                "[BRIDGE] Stream complete: tokens=%d duration_ms=%d ttft_ms=%d action=%s",
                token_count,
                duration_ms,
                ttft_ms,
                action.value,
            )
            pl.llm_completed(
                session_id="", turn_id="",
                duration_ms=duration_ms, token_count=token_count,
                classification=action.value,
            )

        except asyncio.CancelledError:
            logger.info("[BRIDGE] Stream cancelled")
            pl.llm_cancelled(session_id="", turn_id="", reason="stream_cancelled")
            raise

        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "[BRIDGE] Adapter error after %dms: %s",
                duration_ms,
                e,
                exc_info=True,
            )
            pl.llm_error(session_id="", turn_id="", error=str(e)[:200])
            # Emit error acknowledgement so the user isn't left hanging
            chunk_id = f"wttp-{uuid.uuid4().hex[:12]}"
            await self._event_ch.send(ChatChunk(
                id=chunk_id,
                delta=ChoiceDelta(role="assistant", content=_ERROR_ACK),
            ))


# ── Main bridge class ───────────────────────────────────────────────

class WidTTSLLMBridge(LLM):
    """
    Custom LiveKit ``LLM`` implementation for widTTS.

    This is the **only** LiveKit plugin interface widTTS authors.  It
    bridges the LiveKit voice agent pipeline with widTTS's conversation
    policy and LLM infrastructure.

    Parameters
    ----------
    bot:
        Bot configuration dict. Expected keys::

            {
                "system_prompt": str,
                "llm_model": str,
                "llm_provider_id": str,
                "api_key": str,          # optional, from LLM provider
                "base_url": str,         # optional, from LLM provider
                "model": str,            # optional, alias for llm_model
            }

    conversation_adapter:
        An object satisfying :class:`ConversationAdapterProtocol`.
        Responsible for streaming LLM responses.  Typically wraps
        ``AsyncOpenAI``.

    policy:
        The conversation policy that maps interruption classifications
        to concrete actions (stop, repeat, correction, etc.).
    """

    def __init__(
        self,
        *,
        bot: Dict[str, Any],
        conversation_adapter: ConversationAdapterProtocol,
        policy: ConversationPolicy,
    ) -> None:
        super().__init__()
        self._bot = bot
        self._adapter = conversation_adapter
        self._policy = policy

        self._system_prompt: str = bot.get("system_prompt", "")
        self._llm_config: Dict[str, Any] = {
            "api_key": bot.get("api_key", ""),
            "base_url": bot.get("base_url", ""),
            "model": bot.get("model") or bot.get("llm_model", "gpt-4o-mini"),
        }

        logger.info(
            "[BRIDGE] Initialized: model=%s prompt_len=%d",
            self._llm_config["model"],
            len(self._system_prompt),
        )

    # ── LLM interface ───────────────────────────────────────────────

    @property
    def model(self) -> str:
        return self._llm_config.get("model", "unknown")

    @property
    def provider(self) -> str:
        return "widtts"

    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        tools: list | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[Any] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[Dict[str, Any]] = NOT_GIVEN,
    ) -> WidTTSLLMStream:
        """
        Create a streaming response for the given chat context.

        Called by LiveKit's ``VoicePipelineAgent`` when a committed user
        transcript is available.  Returns an ``LLMStream`` that yields
        ``ChatChunk`` objects compatible with livekit-agents.
        """
        logger.info(
            "[BRIDGE] chat() called — ctx_items=%d tools=%d",
            len(getattr(chat_ctx, "items", []) or []),
            len(tools) if tools else 0,
        )

        return WidTTSLLMStream(
            self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
        )


# ── Module-level helpers ────────────────────────────────────────────

def _extract_user_text(chat_ctx: ChatContext) -> str:
    """
    Extract the most recent committed user transcript from the chat context.

    LiveKit's ``ChatContext`` carries a list of messages.  We walk in
    reverse to find the last ``user`` role message — this is the
    committed transcript from the STT pipeline.
    """
    items = getattr(chat_ctx, "items", None) or []
    for item in reversed(items):
        role = getattr(item, "role", None)
        if role == "user" or str(role) == "user":
            # Content can be a string or a list of content parts
            content = getattr(item, "content", None)
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                # Join text content parts
                parts = []
                for part in content:
                    if isinstance(part, str):
                        parts.append(part)
                    elif hasattr(part, "text"):
                        parts.append(part.text)
                return " ".join(parts).strip()
    return ""


def _find_last_assistant_message(chat_ctx: ChatContext) -> Optional[str]:
    """Find the last assistant message for REPEAT action."""
    items = getattr(chat_ctx, "items", None) or []
    for item in reversed(items):
        role = getattr(item, "role", None)
        if role == "assistant" or str(role) == "assistant":
            content = getattr(item, "content", None)
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, str):
                        parts.append(part)
                    elif hasattr(part, "text"):
                        parts.append(part.text)
                text = " ".join(parts).strip()
                if text:
                    return text
    return None


def _build_context_messages(chat_ctx: ChatContext) -> List[Dict[str, str]]:
    """
    Convert ``ChatContext`` items into a plain message list for the
    conversation adapter.

    Returns ``[{"role": "user"|"assistant"|"system", "content": "..."}]``
    suitable for the OpenAI chat completions format.
    """
    messages: List[Dict[str, str]] = []
    items = getattr(chat_ctx, "items", None) or []

    for item in items:
        role = getattr(item, "role", None)
        content = getattr(item, "content", None)

        # Map ChatRole enum to string
        if role == "user" or str(role) == "user":
            role_str = "user"
        elif role == "assistant" or str(role) == "assistant":
            role_str = "assistant"
        elif role == "system" or str(role) == "system":
            role_str = "system"
        else:
            continue  # Skip tool messages and other roles

        # Extract text content
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, str):
                    parts.append(part)
                elif hasattr(part, "text"):
                    parts.append(part.text)
            text = " ".join(parts).strip()
        else:
            continue

        if text:
            messages.append({"role": role_str, "content": text})

    return messages
