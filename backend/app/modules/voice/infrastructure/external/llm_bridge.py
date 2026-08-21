"""
Custom LLM Bridge — the single seam between LiveKit Agents and the platform
business logic.

This implements ``livekit.agents.llm.LLM`` so it can be passed directly to
``AgentSession(llm=...)``. All LLM calls flow through the platform conversation
infrastructure — no livekit-plugins-* LLM backends are ever imported.

Architecture
------------
LiveKit VoicePipelineAgent
    └─ AgentSession(llm=CustomLLMBridge)
        └─ CustomLLMBridge.chat(chat_ctx=...)
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

import asyncio
import logging
import time
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, Union, cast, runtime_checkable

from livekit.agents.llm import ChatChunk, ChoiceDelta, LLM, LLMStream
from livekit.agents.llm.chat_context import ChatContext
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, APIConnectOptions, NotGivenOr

from app.modules.conversation.domain.policy.conversation_policy import (
    ConversationPolicy,
    PolicyAction,
)
from app.shared.config.knobs import knobs
from app.shared.logging import pipeline_logger as pl

logger = logging.getLogger("llm_bridge")


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
        """Stream LLM response tokens for the given user message."""
        ...  # pragma: no cover
        yield ""  # noqa: unreachable


# ── Default Conversation Adapter ─────────────────────────────────────

class DefaultConversationAdapter:
    """
    Independent multi-engine implementation of :class:`ConversationAdapterProtocol`.

    Each provider family is handled independently without forced coupling:
    1. **OpenAI-Compatible Engine** (OpenAI, Groq, OpenRouter, Mistral, Moonshot,
       DeepSeek, Together, Ollama, Google OpenAI endpoint, vLLM, LM Studio, custom proxies):
       Uses direct ``AsyncOpenAI`` with HTTP/2 connection pooling.
    2. **Native Anthropic Engine** (Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus):
       Uses direct async HTTP SSE streaming to Anthropic's ``/v1/messages`` API.
    3. **LiteLLM Engine** (When explicitly selected or configured as proxy):
       Uses ``litellm.acompletion()`` with custom ``api_base`` support.

    Parameters
    ----------
    llm_config:
        LLM provider config with ``api_key``, ``base_url``, ``model``, ``provider_type``.
    """

    def __init__(self, llm_config: Dict[str, Any]) -> None:
        from app.shared.config.knobs import knobs
        from app.shared.constants.provider_urls import PROVIDER_DEFAULT_BASE_URLS

        self._model = llm_config.get("model", knobs.llm.default_model)
        self._api_key = llm_config.get("api_key", "")
        self._provider_type = llm_config.get("provider_type", "")
        
        # Resolve effective base_url
        explicit_url = llm_config.get("base_url") or None
        if explicit_url:
            self._base_url = explicit_url.rstrip("/")
        elif self._provider_type in PROVIDER_DEFAULT_BASE_URLS:
            self._base_url = PROVIDER_DEFAULT_BASE_URLS[self._provider_type]
        else:
            self._base_url = None

        # Pre-initialize AsyncOpenAI client for OpenAI-compatible endpoints
        self._openai_client = None
        if self._base_url and self._provider_type != "anthropic":
            from openai import AsyncOpenAI
            import httpx
            self._openai_client = AsyncOpenAI(
                api_key=self._api_key or "sk-dummy",
                base_url=self._base_url,
                http_client=httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0, connect=5.0),
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                ),
            )

        logger.info(
            "[ADAPTER] Initialized: model=%s provider_type=%s base_url=%s (client=%s)",
            self._model,
            self._provider_type or "unspecified",
            self._base_url or "(native/direct)",
            "AnthropicNative" if self._provider_type == "anthropic" else ("AsyncOpenAI" if self._openai_client else "dynamic"),
        )

    async def _stream_openai_compatible(
        self,
        *,
        model: str,
        api_key: Optional[str],
        base_url: Optional[str],
        messages: List[Dict[str, Any]],
    ) -> AsyncIterator[str]:
        """Stream from any OpenAI-compatible endpoint using AsyncOpenAI."""
        from openai import AsyncOpenAI
        import httpx

        client = self._openai_client
        if not client or (base_url and str(client.base_url).rstrip('/') != base_url.rstrip('/')):
            client = AsyncOpenAI(
                api_key=api_key or "sk-dummy",
                base_url=base_url,
                http_client=httpx.AsyncClient(
                    timeout=httpx.Timeout(30.0, connect=5.0),
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                ),
            )

        response = await client.chat.completions.create(
            model=model,
            messages=cast(Any, messages),
            stream=True,
            temperature=knobs.llm.temperature,
            top_p=knobs.llm.top_p,
        )
        async for chunk in response:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                token = getattr(delta, "content", None)
                if token:
                    yield token

    async def _stream_anthropic(
        self,
        *,
        model: str,
        api_key: Optional[str],
        base_url: Optional[str],
        system_prompt: str,
        context: List[Dict[str, str]],
        user_text: str,
    ) -> AsyncIterator[str]:
        """Stream directly from Anthropic /v1/messages API via async SSE."""
        import json
        import httpx

        endpoint = f"{(base_url or 'https://api.anthropic.com/v1').rstrip('/')}/messages"
        headers = {
            "x-api-key": api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "accept": "text/event-stream",
        }

        # Build clean Anthropic messages (alternating user/assistant)
        anthropic_messages: List[Dict[str, str]] = []
        for msg in context:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                anthropic_messages.append({"role": role, "content": content})

        if not anthropic_messages or anthropic_messages[-1].get("content") != user_text:
            anthropic_messages.append({"role": "user", "content": user_text})

        payload = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": knobs.llm.max_tokens or 1024,
            "stream": True,
            "temperature": knobs.llm.temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            async with client.stream("POST", endpoint, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    raise RuntimeError(f"Anthropic API Error ({resp.status_code}): {err_body.decode('utf-8', errors='ignore')}")
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            event_data = json.loads(data_str)
                            if event_data.get("type") == "content_block_delta":
                                delta = event_data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    text = delta.get("text")
                                    if text:
                                        yield text
                        except Exception:
                            continue

    async def _stream_litellm(
        self,
        *,
        model: str,
        api_key: Optional[str],
        base_url: Optional[str],
        messages: List[Dict[str, Any]],
    ) -> AsyncIterator[str]:
        """Stream via LiteLLM multi-provider router when explicitly selected."""
        import os
        os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
        try:
            import litellm
            litellm.telemetry = False
            litellm.suppress_debug_info = True
        except Exception:
            pass

        import litellm
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": knobs.llm.stream,
            "temperature": knobs.llm.temperature,
            "top_p": knobs.llm.top_p,
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

    async def stream_chat(
        self,
        *,
        user_text: str,
        system_prompt: str,
        context: List[Dict[str, str]],
        llm_config: Dict[str, Any],
    ) -> AsyncIterator[str]:
        """Route and stream LLM response tokens through the appropriate independent engine."""
        from app.shared.constants.provider_urls import PROVIDER_DEFAULT_BASE_URLS

        messages: List[Any] = []

        # Check if a system message already exists in context to prevent duplicate injection
        has_system = any(msg.get("role") == "system" for msg in context)
        if not has_system and system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        for msg in context:
            content = msg.get("content", "")
            if not content:
                continue
            # If system message is in context but empty, replace with system_prompt
            if msg.get("role") == "system" and system_prompt and len(content.strip()) < 10:
                messages.append({"role": "system", "content": system_prompt})
            else:
                messages.append({"role": msg.get("role", "user"), "content": content})

        # Append user_text only if it isn't already present at the end of context
        if not messages or messages[-1].get("content") != user_text:
            messages.append({"role": "user", "content": user_text})

        model = llm_config.get("model") or self._model
        api_key = llm_config.get("api_key") or self._api_key or None
        provider_type = llm_config.get("provider_type") or self._provider_type or ""

        explicit_url = llm_config.get("base_url") or self._base_url or None
        if explicit_url:
            base_url = explicit_url.rstrip("/")
        elif provider_type in PROVIDER_DEFAULT_BASE_URLS:
            base_url = PROVIDER_DEFAULT_BASE_URLS[provider_type]
        else:
            base_url = None

        try:
            # 1. Native Anthropic Engine
            if provider_type == "anthropic" or (not base_url and model.startswith("claude-")):
                async for token in self._stream_anthropic(
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    system_prompt=system_prompt,
                    context=context,
                    user_text=user_text,
                ):
                    yield token
                return

            # 2. LiteLLM Engine (when explicitly configured as provider)
            if provider_type in ("litellm", "litellm_proxy"):
                async for token in self._stream_litellm(
                    model=model,
                    api_key=api_key,
                    base_url=base_url,
                    messages=messages,
                ):
                    yield token
                return

            # 3. Direct OpenAI-Compatible Engine (Default for OpenAI, Groq, OpenRouter, Mistral, Moonshot, Ollama, DeepSeek, Together, Google, custom base_url)
            async for token in self._stream_openai_compatible(
                model=model,
                api_key=api_key,
                base_url=base_url or "https://api.openai.com/v1",
                messages=messages,
            ):
                yield token

        except asyncio.CancelledError:
            raise
        except Exception as e:
            err_msg = str(e)
            if "Use litellm._turn_on_debug()" in err_msg:
                err_msg = err_msg.split("Use litellm._turn_on_debug()")[0].strip()
            logger.error("[ADAPTER] LLM stream error (provider=%s model=%s base_url=%s): %s", provider_type or "default", model, base_url or "direct", err_msg)
            yield knobs.llm.error_fallback_text


# ── Policy response constants (wired from knobs) ────────────────────

from app.shared.config.knobs import knobs as _knobs

_STOP_ACK = _knobs.llm.stop_ack_text
_END_ACK = _knobs.llm.end_ack_text
_REPEAT_FALLBACK = _knobs.llm.repeat_fallback_text
_ERROR_ACK = _knobs.llm.error_fallback_text

_FAREWELL_MARKER = _knobs.llm.farewell_marker


# ── LLMStream subclass ──────────────────────────────────────────────

class CustomLLMStream(LLMStream):
    """
    Concrete ``LLMStream`` that routes through platform business logic.

    Created by ``CustomLLMBridge.chat()``. The ``_run()`` method extracts
    the transcript, runs policy classification, and either yields a
    pre-formed response or streams from the conversation adapter.
    """

    def __init__(
        self,
        bridge: "CustomLLMBridge",
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

        turn_id = f"turn-{uuid.uuid4().hex[:8]}"
        session_id = self._bridge._session_id

        logger.info(
            "[BRIDGE] Processing user text [session=%s turn=%s]: %s (len=%d)",
            session_id,
            turn_id,
            user_text[:120],
            len(user_text),
        )
        pl.llm_started(session_id=session_id, turn_id=turn_id)

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
            response_text = None  # Let the LLM generate its own farewell in character

        elif action == PolicyAction.REPEAT:
            response_text = _find_last_assistant_message(chat_ctx) or _REPEAT_FALLBACK

        elif action in (PolicyAction.CORRECTION, PolicyAction.FORGET):
            response_text = None  # Let the LLM handle corrections naturally

        # 4. Emit pre-formed response if we have one (policy shortcut)
        if response_text is not None:
            chunk_id = f"stream-{uuid.uuid4().hex[:12]}"
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
            # END_CONVERSATION policy → schedule session end
            if action == PolicyAction.END_CONVERSATION and self._bridge._on_session_end:
                logger.info("[BRIDGE] END_CONVERSATION policy — scheduling session end in 5s")
                self._bridge._on_session_end()
            return

        # 5. Normal answer / correction / continue — delegate to adapter
        try:
            context_messages = _build_context_messages(chat_ctx)
            token_count = 0
            first_token_time: Optional[float] = None
            full_response = ""
            stream_buffer = ""

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

                full_response += token
                stream_buffer += token

                # Strip complete farewell marker if present
                if _FAREWELL_MARKER in stream_buffer:
                    stream_buffer = stream_buffer.replace(_FAREWELL_MARKER, "")

                # Hold back any trailing prefix that could be part of [END_SESSION]
                hold_back_len = 0
                for i in range(1, len(_FAREWELL_MARKER)):
                    prefix = _FAREWELL_MARKER[:i]
                    if stream_buffer.endswith(prefix):
                        hold_back_len = len(prefix)
                        break

                if hold_back_len > 0:
                    emit_text = stream_buffer[:-hold_back_len]
                    stream_buffer = stream_buffer[-hold_back_len:]
                else:
                    emit_text = stream_buffer
                    stream_buffer = ""

                if emit_text:
                    token_count += 1
                    chunk_id = f"stream-{uuid.uuid4().hex[:12]}"
                    await self._event_ch.send(ChatChunk(
                        id=chunk_id,
                        delta=ChoiceDelta(role="assistant", content=emit_text),
                    ))

            # Flush remaining buffer after stream finishes (stripping marker)
            if stream_buffer:
                clean_tail = stream_buffer.replace(_FAREWELL_MARKER, "")
                if clean_tail:
                    token_count += 1
                    chunk_id = f"stream-{uuid.uuid4().hex[:12]}"
                    await self._event_ch.send(ChatChunk(
                        id=chunk_id,
                        delta=ChoiceDelta(role="assistant", content=clean_tail),
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
                session_id=session_id, turn_id=turn_id,
                duration_ms=duration_ms, token_count=token_count,
                classification=action.value,
            )

            # Check if the response contains the farewell marker
            if self._bridge._on_session_end and _FAREWELL_MARKER in full_response:
                logger.info("[BRIDGE] Farewell detected — scheduling session end in 5s")
                self._bridge._on_session_end()

        except asyncio.CancelledError:
            logger.info("[BRIDGE] Stream cancelled")
            pl.llm_cancelled(session_id=session_id, turn_id=turn_id, reason="stream_cancelled")
            raise

        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.error(
                "[BRIDGE] Adapter error after %dms: %s",
                duration_ms,
                e,
                exc_info=True,
            )
            pl.llm_error(session_id=session_id, turn_id=turn_id, error=str(e)[:200])
            chunk_id = f"stream-{uuid.uuid4().hex[:12]}"
            await self._event_ch.send(ChatChunk(
                id=chunk_id,
                delta=ChoiceDelta(role="assistant", content=_ERROR_ACK),
            ))


# ── Main bridge class ───────────────────────────────────────────────

class CustomLLMBridge(LLM):
    """
    Custom LiveKit ``LLM`` implementation.

    Bridges the LiveKit voice agent pipeline with the conversation policy
    and LiteLLM infrastructure.

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
        Responsible for streaming LLM responses.

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
        session_id: str = "",
        on_session_end: Optional[Any] = None,
    ) -> None:
        super().__init__()
        self._bot = bot
        self._adapter = conversation_adapter
        self._policy = policy
        self._session_id = session_id
        self._on_session_end = on_session_end

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
        return "custom"

    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        tools: list | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[Any] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[Dict[str, Any]] = NOT_GIVEN,
    ) -> CustomLLMStream:
        """
        Create a streaming response for the given chat context.

        Called by LiveKit's ``VoicePipelineAgent`` when a committed user
        transcript is available. Returns an ``LLMStream`` yielding ``ChatChunk``
        objects compatible with livekit-agents.
        """
        logger.info(
            "[BRIDGE] chat() called — ctx_items=%d tools=%d",
            len(getattr(chat_ctx, "items", []) or []),
            len(tools) if tools else 0,
        )

        return CustomLLMStream(
            self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
        )


# ── Module-level helpers ────────────────────────────────────────────

def _extract_user_text(chat_ctx: Any) -> str:
    """Extract the most recent committed user transcript from the chat context."""
    items = getattr(chat_ctx, "items", None) or []
    for item in reversed(items):
        role = getattr(item, "role", None)
        if role == "user" or str(role) == "user":
            content = getattr(item, "content", None)
            if isinstance(content, str):
                return content.strip()
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, str):
                        parts.append(part)
                    elif hasattr(part, "text"):
                        parts.append(part.text)
                return " ".join(parts).strip()
    return ""


def _find_last_assistant_message(chat_ctx: Any) -> Optional[str]:
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


def _build_context_messages(chat_ctx: Any) -> List[Dict[str, str]]:
    """Convert ``ChatContext`` items into a plain message list for the conversation adapter."""
    messages: List[Dict[str, str]] = []
    items = getattr(chat_ctx, "items", None) or []

    for item in items:
        role = getattr(item, "role", None)
        content = getattr(item, "content", None)

        if role == "user" or str(role) == "user":
            role_str = "user"
        elif role == "assistant" or str(role) == "assistant":
            role_str = "assistant"
        elif role == "system" or str(role) == "system":
            role_str = "system"
        else:
            continue

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
