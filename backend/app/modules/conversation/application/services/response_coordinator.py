import asyncio
import json
import re
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

from app.shared.events.event_bus import EventBus, Event
from app.shared.logging import pipeline_logger as pl
from app.shared.cancellation.cancellation_token import CancellationToken

logger = logging.getLogger("response_coordinator")


@dataclass
class StreamingResult:
    classification: str = ""
    should_advance: bool = False
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    duration_ms: int = 0
    time_to_first_token_ms: Optional[int] = None
    time_to_first_audio_ms: Optional[int] = None


class ResponseCoordinator:
    """Owns the LLM → TTS streaming pipeline."""

    DELIMITER = "###METADATA###"

    def __init__(self, event_bus: EventBus, synthesize_speech, validate_response_stream):
        self._bus = event_bus
        self._synthesize_speech = synthesize_speech
        self._validate_response_stream = validate_response_stream
        self._token: Optional[CancellationToken] = None
        self._cancelled = False

    def set_cancellation_token(self, token: CancellationToken) -> None:
        self._token = token

    def cancel(self, reason: str = "cancelled") -> None:
        self._cancelled = True
        if self._token:
            self._token.cancel(reason)

    async def stream_response(self, item, transcript, session_id, turn_id, question_id,
                              turn_context=None) -> StreamingResult:
        result = StreamingResult()

        full_buffer: list[str] = []
        spoken_sentences: list[str] = []
        current_sentence: list[str] = []
        token_count = 0
        first_token_time: Optional[float] = None
        first_audio_time: Optional[float] = None
        meta_sent = False
        _llm_t0 = time.monotonic()
        delimiter_found = False

        pl.llm_started(session_id, turn_id)
        pl.validation_start(session_id, turn_id, question_id, transcript)

        await self._bus.publish_raw("llm_stream_started", {
            "session_id": session_id, "turn_id": turn_id, "question_id": question_id
        }, session_id)

        try:
            async for token in self._validate_response_stream(
                item["type"], item["text"], item.get("expected_context", ""), transcript
            ):
                if self._token and self._token.is_cancelled:
                    raise asyncio.CancelledError(f"CancellationToken: {self._token.reason}")
                if self._cancelled:
                    raise asyncio.CancelledError("ResponseCoordinator cancelled")
                if turn_context is not None and getattr(turn_context, "is_destroyed", False):
                    break

                token_count += 1
                if first_token_time is None:
                    first_token_time = time.monotonic()
                    pl.llm_token(session_id, turn_id, token, 0)
                    if not meta_sent:
                        meta_sent = True
                        await self._bus.publish_raw(
                            "tts_audio_meta", {"text": "", "is_streaming": True, "chunk_count": 0}, session_id
                        )

                full_buffer.append(token)
                combined = "".join(full_buffer)

                if self.DELIMITER in combined:
                    parts = combined.split(self.DELIMITER, 1)
                    spoken_text = parts[0]
                    metadata_text = parts[1] if len(parts) > 1 else ""

                    if not delimiter_found:
                        already_spoken = "".join(spoken_sentences)
                        new_spoken = spoken_text[len(already_spoken):]
                        if new_spoken:
                            text_to_speak = new_spoken.strip()
                            if text_to_speak:
                                if first_audio_time is None:
                                    first_audio_time = time.monotonic()
                                await self._tts_flush(text_to_speak, session_id, turn_id)
                                spoken_sentences.append(text_to_speak)
                        delimiter_found = True

                    metadata_stripped = metadata_text.strip()
                    if not metadata_stripped or "{" not in metadata_stripped:
                        continue

                    # Wait for balanced braces — JSON may still be streaming
                    open_count = metadata_stripped.count("{")
                    close_count = metadata_stripped.count("}")
                    if open_count > close_count:
                        continue  # JSON incomplete, wait for more tokens

                    result.duration_ms = int((time.monotonic() - _llm_t0) * 1000)
                    pl.llm_completed(session_id, turn_id, result.duration_ms, token_count)

                    await self._bus.publish_raw(
                        "tts_stream_end", {"text": "", "chunks": 0, "bytes": 0}, session_id
                    )

                    try:
                        json_start = metadata_stripped.index("{")
                        raw_json = metadata_stripped[json_start:]
                        parsed = self._lenient_json_parse(raw_json)
                        result.metadata = parsed
                        result.classification = parsed.get("classification", "?")
                        if "should_advance" in parsed:
                            result.should_advance = bool(parsed.get("should_advance"))
                        else:
                            _REJECT = {"IRRELEVANT", "OFF_TOPIC", "USER_REFUSED", "SYSTEM_ERROR", "NEEDS_CLARIFICATION", "USER_DID_NOT_UNDERSTAND", "USER_DOES_NOT_KNOW"}
                            result.should_advance = parsed.get("classification", "") not in _REJECT
                        result.reason = parsed.get("reason") or parsed.get("reasoning", "")
                        result.token_count = token_count
                        if first_token_time and first_audio_time:
                            result.time_to_first_token_ms = int((first_token_time - _llm_t0) * 1000)
                            result.time_to_first_audio_ms = int((first_audio_time - _llm_t0) * 1000)
                    except Exception as e:
                        logger.error(f"[RESPONSE_COORD] Metadata parse error: {e}")
                        result.metadata = self._fallback_metadata(str(e))
                        result.classification = "SYSTEM_ERROR"

                    await self._bus.publish_raw("llm_stream_completed", {
                        "session_id": session_id, "turn_id": turn_id,
                        "duration_ms": result.duration_ms, "token_count": token_count,
                        "classification": result.classification,
                    }, session_id)
                    return result

                if not delimiter_found:
                    current_sentence.append(token)
                    sentence_text = "".join(current_sentence)
                    flush_now = token.endswith((".", "!", "?", "\n")) or len(sentence_text) >= 80
                    if flush_now:
                        text_to_speak = sentence_text.strip()
                        # Skip trivial/empty sentences (just punctuation, single chars, etc.)
                        stripped_alpha = ''.join(c for c in text_to_speak if c.isalnum())
                        if text_to_speak and stripped_alpha:
                            if first_audio_time is None:
                                first_audio_time = time.monotonic()
                            await self._tts_flush(text_to_speak, session_id, turn_id)
                            spoken_sentences.append(text_to_speak)
                        current_sentence = []

            remaining = "".join(current_sentence).strip()
            if remaining:
                await self._tts_flush(remaining, session_id, turn_id)
                spoken_sentences.append(remaining)

            result.duration_ms = int((time.monotonic() - _llm_t0) * 1000)
            pl.llm_completed(session_id, turn_id, result.duration_ms, token_count)
            result.metadata = self._no_delimiter_fallback()
            result.classification = "SYSTEM_ERROR"

            await self._bus.publish_raw("tts_stream_end", {"text": "", "chunks": 0, "bytes": 0}, session_id)
            return result

        except asyncio.CancelledError:
            pl.llm_cancelled(session_id, turn_id, "response_coordinator_cancelled")
            raise

    async def _tts_flush(self, text, session_id, turn_id):
        try:
            async for chunk in self._synthesize_speech.synthesize_stream(text):
                if not chunk:
                    continue
                await self._bus.publish_raw("tts_audio_chunk", {
                    "session_id": session_id, "turn_id": turn_id,
                    "chunk": chunk, "bytes": len(chunk)
                }, session_id)
        except Exception as e:
            logger.error(f"[RESPONSE_COORD] TTS error: {e}")
            try:
                audio = await self._synthesize_speech.execute(text)
                await self._bus.publish_raw("tts_audio_chunk", {
                    "session_id": session_id, "turn_id": turn_id,
                    "chunk": audio, "bytes": len(audio)
                }, session_id)
            except Exception as e2:
                logger.error(f"[RESPONSE_COORD] REST fallback also failed: {e2}")

    @staticmethod
    def _lenient_json_parse(raw: str) -> Dict[str, Any]:
        """Parse JSON with fallbacks for common LLM output quirks."""
        # 0. Clean markdown code blocks and extract first '{' to last '}'
        cleaned = raw.strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

        # 1. Try strict parse
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # 2. Try replacing single quotes with double quotes
        try:
            return json.loads(cleaned.replace("'", '"'))
        except (json.JSONDecodeError, ValueError):
            pass

        # 3. Try fixing unquoted keys: {key: val} → {"key": val}
        try:
            fixed = re.sub(r'(?<=[{,])\s*(\w+)\s*:', r' "\1":', cleaned)
            # Also fix Python booleans/None
            fixed = fixed.replace(": True", ": true").replace(": False", ": false").replace(": None", ": null")
            return json.loads(fixed)
        except (json.JSONDecodeError, ValueError):
            pass

        # 4. Give up
        raise ValueError(f"Could not parse JSON: {raw[:200]}")

    @staticmethod
    def _fallback_metadata(error):
        return {
            "understood_intent": "Metadata parse failed.", "answered": False,
            "classification": "SYSTEM_ERROR", "relevance": 0.0, "completeness": 0.0,
            "missing_information": ["Parse error."], "should_repeat_question": True,
            "should_follow_up": False, "follow_up_question": None, "should_advance": False,
            "reason": "I didn't catch that. Could you say that again?",
            "reasoning": f"Metadata parse failed: {error}", "valid": False, "advance": False,
        }

    @staticmethod
    def _no_delimiter_fallback():
        return {
            "understood_intent": "No metadata delimiter found.", "answered": False,
            "classification": "SYSTEM_ERROR", "relevance": 0.0, "completeness": 0.0,
            "missing_information": ["No metadata found."], "should_repeat_question": True,
            "should_follow_up": False, "follow_up_question": None, "should_advance": False,
            "reason": "I didn't catch that. Could you say that again?",
            "reasoning": "LLM stream ended without metadata delimiter.", "valid": False, "advance": False,
        }

    async def stream_bot_response(self, transcript, session_id, turn_id,
                                   system_prompt, llm_config, context=None,
                                   turn_context=None) -> Dict[str, Any]:
        """
        Bot-driven conversation: stream LLM response directly to TTS.

        Unlike stream_response(), there's no metadata delimiter.
        The system prompt IS the conversation logic — the LLM just generates
        a natural response that gets spoken directly.
        """
        import litellm

        full_response: list[str] = []
        spoken_sentences: list[str] = []
        current_sentence: list[str] = []
        token_count = 0
        first_token_time: Optional[float] = None
        _llm_t0 = time.monotonic()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation context if available
        if context:
            for msg in context:
                messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

        # Add current user message
        messages.append({"role": "user", "content": transcript})

        model = llm_config.get("model", "gpt-4o-mini")
        api_key = llm_config.get("api_key", "")
        base_url = llm_config.get("base_url", "")

        try:
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=api_key,
                api_base=base_url if base_url else None,
                stream=True,
            )

            async for chunk in response:
                if self._token and self._token.is_cancelled:
                    raise asyncio.CancelledError(f"CancellationToken: {self._token.reason}")
                if turn_context is not None and getattr(turn_context, "is_destroyed", False):
                    break

                delta = chunk.choices[0].delta
                token = getattr(delta, "content", None)
                if not token:
                    continue

                token_count += 1
                if first_token_time is None:
                    first_token_time = time.monotonic()

                full_response.append(token)
                current_sentence.append(token)
                sentence_text = "".join(current_sentence)

                # Flush at sentence boundaries for natural TTS pacing
                flush_now = token.endswith((".", "!", "?", "\n")) or len(sentence_text) >= 80
                if flush_now:
                    text_to_speak = sentence_text.strip()
                    stripped_alpha = ''.join(c for c in text_to_speak if c.isalnum())
                    if text_to_speak and stripped_alpha:
                        await self._tts_flush(text_to_speak, session_id, turn_id)
                        spoken_sentences.append(text_to_speak)
                    current_sentence = []

            # Flush remaining text
            remaining = "".join(current_sentence).strip()
            if remaining:
                await self._tts_flush(remaining, session_id, turn_id)
                spoken_sentences.append(remaining)

            await self._bus.publish_raw(
                "tts_stream_end", {"text": "", "chunks": 0, "bytes": 0}, session_id
            )

            return {"text": "".join(full_response).strip(), "token_count": token_count}

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[BOT_RESPONSE] LLM error: {e}")
            return {"text": "", "error": str(e)}
