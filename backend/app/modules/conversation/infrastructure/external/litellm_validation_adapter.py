import json
import re
import time
import asyncio
from typing import Dict, Any, AsyncGenerator, Optional
from openai import AsyncOpenAI
from app.shared.logging.logger import logger
from app.modules.conversation.domain.interfaces.validation_provider_interface import ValidationProviderInterface
from app.modules.conversation.infrastructure.external.prompts import (
    VALIDATION_SYSTEM_PROMPT,
    build_validation_user_message,
)

DANGLING_ENDINGS = {
    # Conjunctions left hanging (incomplete without a clause)
    "because", "and", "but", "so", "or", "if", "that", "when", "while",
    "although", "though", "as", "since", "unless",
    # Lead-in carrier phrases (incomplete without an object)
    "call me a", "going to", "went to", "i am going to",
}


class LiteLLMValidationAdapter(ValidationProviderInterface):

    def __init__(self):
        self._client = None
        self._llm_config: Optional[Dict[str, Any]] = None

    def set_llm_config(self, config: Dict[str, Any]) -> None:
        """Inject LLM config from bot at session startup."""
        self._llm_config = config
        # Reset client so it picks up new config
        self._client = None

    def _get_client(self) -> AsyncOpenAI:
        if not self._client:
            api_key = "dummy_key"
            base_url = "https://api.openai.com/v1"
            if self._llm_config:
                api_key = self._llm_config.get("api_key", api_key)
                base_url = self._llm_config.get("base_url", base_url) or base_url
            self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        return self._client

    def _get_model(self) -> str:
        if self._llm_config:
            return self._llm_config.get("model", "gpt-4o-mini")
        return "gpt-4o-mini"

    async def validate(
        self, item_type: str, item_text: str, expected_context: str, user_response: str
    ) -> Dict[str, Any]:
        if not user_response or not user_response.strip():
            return {
                "understood_intent": "User provided empty audio or no response.",
                "answered": False,
                "classification": "SYSTEM_ERROR",
                "relevance": 0.0,
                "completeness": 0.0,
                "missing_information": ["Response was empty."],
                "should_repeat_question": True,
                "should_follow_up": False,
                "follow_up_question": None,
                "should_advance": False,
                "reason": "I didn't catch that. Could you say that again?",
                "reasoning": "User response was empty.",
                "valid": False,
            }

        cleaned_resp = user_response.strip().lower()
        stripped = re.sub(r'[^a-z0-9 ]', '', cleaned_resp).strip()

        user_content = build_validation_user_message(item_type, item_text, expected_context, user_response)
        client = self._get_client()

        _llm_t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self._get_model(),
                    messages=[
                        {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    max_tokens=2048,
                    timeout=12,
                ),
                timeout=15.0,
            )
            choice = response.choices[0]
            msg = choice.message

            text = msg.content or ""
            if not text.strip():
                text = getattr(msg, "reasoning_content", "") or ""
            if not text.strip():
                extras = getattr(msg, "model_extra", {}) or {}
                text = extras.get("reasoning_content", "") or ""
            if not text.strip():
                psf = getattr(msg, "provider_specific_fields", {}) or {}
                if not psf:
                    psf = (getattr(msg, "model_extra", {}) or {}).get("provider_specific_fields", {}) or {}
                text = psf.get("reasoning_content", "") or ""

            text = text.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                text = match.group(0)

            parsed = json.loads(text)
            _llm_ms = int((time.monotonic() - _llm_t0) * 1000)
            logger.info(f"[VALIDATION LLM] LLM responded in {_llm_ms}ms | classification={parsed.get('classification', '?')} | advance={parsed.get('should_advance', '?')}")

            understood_intent = str(parsed.get("understood_intent", ""))
            answered = bool(parsed.get("answered", False))
            classification = str(parsed.get("classification", "NEEDS_CLARIFICATION"))
            relevance = float(parsed.get("relevance", 0.0))
            completeness = float(parsed.get("completeness", 0.0))
            missing_info = parsed.get("missing_information", [])
            should_repeat = bool(parsed.get("should_repeat_question", False))
            should_follow_up = bool(parsed.get("should_follow_up", False))
            follow_up_q = parsed.get("follow_up_question")
            llm_advance = bool(parsed.get("should_advance", False))
            reasoning = str(parsed.get("reasoning", ""))

            _REJECT_CLASSES = {"IRRELEVANT", "OFF_TOPIC", "USER_REFUSED", "SYSTEM_ERROR", "NEEDS_CLARIFICATION", "USER_DID_NOT_UNDERSTAND", "USER_DOES_NOT_KNOW"}
            should_advance = classification not in _REJECT_CLASSES

            if should_follow_up and follow_up_q:
                spoken_reason = str(follow_up_q)
            elif should_repeat:
                spoken_reason = f"I didn't catch that clearly. {item_text}"
            elif reasoning:
                spoken_reason = reasoning
            else:
                spoken_reason = f"Could you tell me a bit more about {item_text}?"

            return {
                "understood_intent": understood_intent,
                "answered": answered,
                "classification": classification,
                "relevance": relevance,
                "completeness": completeness,
                "missing_information": missing_info,
                "should_repeat_question": should_repeat,
                "should_follow_up": should_follow_up,
                "follow_up_question": follow_up_q,
                "should_advance": should_advance,
                "reason": spoken_reason if not should_advance else "Got it.",
                "reasoning": reasoning,
                "valid": should_advance,
                "advance": should_advance,
            }

        except (asyncio.TimeoutError, Exception) as e:
            is_timeout = isinstance(e, asyncio.TimeoutError)
            logger.warning(
                f"[VALIDATION {'TIMEOUT' if is_timeout else 'ERROR'}] "
                f"LLM unavailable for: '{user_response[:80]}' — {e}. "
                f"Falling back to graceful degradation."
            )

            words = stripped.split()
            if len(words) >= 2:
                return {
                    "understood_intent": f"User provided response: {user_response} (LLM unavailable, accepted by fallback)",
                    "answered": True,
                    "classification": "FULLY_ANSWERED",
                    "relevance": 0.8,
                    "completeness": 0.8,
                    "missing_information": [],
                    "should_repeat_question": False,
                    "should_follow_up": False,
                    "follow_up_question": None,
                    "should_advance": True,
                    "reason": "Got it.",
                    "reasoning": f"LLM unavailable. Graceful degradation: multi-word response passed all deterministic guards.",
                    "valid": True,
                    "advance": True,
                }
            else:
                return {
                    "understood_intent": f"User said: {user_response} (LLM unavailable)",
                    "answered": False,
                    "classification": "NEEDS_CLARIFICATION",
                    "relevance": 0.5,
                    "completeness": 0.3,
                    "missing_information": ["More detail needed."],
                    "should_repeat_question": False,
                    "should_follow_up": True,
                    "follow_up_question": "Could you tell me a bit more?",
                    "should_advance": False,
                    "reason": "Could you tell me a bit more?",
                    "reasoning": f"LLM unavailable. Graceful degradation: single-word response, requesting clarification.",
                    "valid": False,
                    "advance": False,
                }

    # ── Streaming validation ──

    async def validate_stream(
        self, item_type: str, item_text: str, expected_context: str, user_response: str
    ) -> AsyncGenerator[str, None]:
        """Streaming LLM validation yielding natural-language tokens + JSON metadata."""
        user_content = build_validation_user_message(item_type, item_text, expected_context, user_response)
        client = self._get_client()

        _llm_t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self._get_model(),
                    messages=[
                        {"role": "system", "content": VALIDATION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    max_tokens=4096,
                    timeout=12,
                    stream=True,
                ),
                timeout=30.0,
            )

            logger.info(f"[VALIDATION STREAM] LLM connection established. Awaiting chunks...")
            chunk_count = 0
            content_count = 0
            reasoning_count = 0
            first_chunk_at = None
            first_content_at = None
            t_connect_ms = 0
            async for chunk in response:
                delta = chunk.choices[0].delta
                if chunk_count == 0:
                    first_chunk_at = time.monotonic()
                    t_connect_ms = int((first_chunk_at - _llm_t0) * 1000)
                    rc = getattr(delta, 'reasoning_content', None)
                    c = delta.content
                    logger.info(f"[VALIDATION STREAM] First chunk arrived in {t_connect_ms}ms — content={repr(c)[:60]} reasoning_content={repr(rc)[:60]}")
                chunk_count += 1
                token = delta.content or ""
                if not token:
                    rc = getattr(delta, 'reasoning_content', None)
                    if rc:
                        reasoning_count += 1
                else:
                    if content_count == 0:
                        first_content_at = time.monotonic()
                        t_content_ms = int((first_content_at - _llm_t0) * 1000)
                        logger.info(f"[VALIDATION STREAM] First content token arrived in {t_content_ms}ms — model spent {t_content_ms - t_connect_ms}ms reasoning ({reasoning_count} reasoning chunks)")
                    content_count += 1
                    yield token

            _llm_ms = int((time.monotonic() - _llm_t0) * 1000)
            logger.info(f"[VALIDATION STREAM] LLM stream completed in {_llm_ms}ms | chunks={chunk_count} content_chunks={content_count} reasoning_chunks={reasoning_count}")

        except (asyncio.TimeoutError, Exception) as e:
            is_timeout = isinstance(e, asyncio.TimeoutError)
            logger.warning(
                f"[VALIDATION STREAM {'TIMEOUT' if is_timeout else 'ERROR'}] "
                f"LLM stream failed: {e}. Emitting fallback."
            )
            yield "I didn't quite catch that. Could you say that again?"
            yield "###METADATA###"
            yield json.dumps({
                "understood_intent": "LLM stream failed.",
                "answered": False,
                "classification": "SYSTEM_ERROR",
                "relevance": 0.0,
                "completeness": 0.0,
                "missing_information": ["LLM unavailable."],
                "should_repeat_question": True,
                "should_follow_up": False,
                "follow_up_question": None,
                "should_advance": False,
                "reason": "I didn't catch that. Could you say that again?",
                "reasoning": f"LLM stream failed: {e}",
                "valid": False,
                "advance": False,
            })
