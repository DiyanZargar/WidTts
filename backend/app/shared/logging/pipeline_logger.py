"""Structured pipeline event logger for deterministic debugging and replay.

Every major pipeline event is logged with a consistent schema:
    timestamp | event=EVENT_TYPE | session_id | turn_id |
    component=... | severity=... | details...

This logger observes widTTS BUSINESS events only:
- Session lifecycle
- Conversation lifecycle
- Turn lifecycle
- Question presentation
- Transcript ownership (acceptance/rejection)
- FSM transitions
- Interruption classification
- LLM requests and responses
- Validation pipeline
- Correction pipeline
- Error diagnostics
- Latency metrics
- Resource lifecycle

LiveKit infrastructure events (STT execution, TTS synthesis, audio transport,
WebSocket connection, playback) are NOT logged here — LiveKit owns those.
"""

import time
from app.shared.logging.logger import logger


# ── Internal helpers ──


def _ts() -> str:
    """Return a millisecond-precision timestamp string."""
    return (
        time.strftime("%H:%M:%S", time.localtime())
        + f".{int(time.time() * 1000) % 1000:03d}"
    )


def _fmt(
    event_type: str,
    session_id: str = "",
    turn_id: str = "",
    component: str = "pipeline",
    severity: str = "INFO",
    **kwargs,
) -> str:
    """Build the structured field string.

    All IDs are FULL (not truncated) so that a single grep on a UUID
    returns every log line for that conversation / turn.
    """
    parts = [f"event={event_type}"]
    if session_id:
        parts.append(f"session_id={session_id}")
        parts.append(f"conversation_id={session_id}")
    if turn_id:
        parts.append(f"turn_id={turn_id}")
    parts.append(f"component={component}")
    parts.append(f"severity={severity}")
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    return " | ".join(parts)


def _log(
    event_type: str,
    session_id: str = "",
    turn_id: str = "",
    component: str = "pipeline",
    severity: str = "INFO",
    **kwargs,
) -> None:
    """Emit a single structured pipeline log line at the appropriate level."""
    msg = f"[PIPELINE] {_ts()} | {_fmt(event_type, session_id, turn_id, component, severity, **kwargs)}"
    if severity == "ERROR":
        logger.error(msg)
    elif severity == "WARNING":
        logger.warning(msg)
    else:
        logger.info(msg)


# ── Session lifecycle ──


def session_start(
    session_id: str, conversation_type: str, is_recovery: bool
) -> None:
    _log(
        "SESSION_START",
        session_id=session_id,
        component="session",
        type=conversation_type,
        recovery=is_recovery,
    )


def session_end(session_id: str, reason: str) -> None:
    _log("SESSION_END", session_id=session_id, component="session", reason=reason)


# ── Conversation lifecycle ──


def conversation_start(session_id: str, conversation_type: str) -> None:
    _log(
        "CONVERSATION_START",
        session_id=session_id,
        component="conversation",
        type=conversation_type,
    )


def conversation_end(session_id: str, reason: str) -> None:
    _log(
        "CONVERSATION_END",
        session_id=session_id,
        component="conversation",
        reason=reason,
    )


# ── Turn lifecycle ──


def turn_create(
    turn_id: str,
    session_id: str,
    question_id: str,
    sequence: int,
    question_text: str,
) -> None:
    _log(
        "TURN_CREATE",
        session_id=session_id,
        turn_id=turn_id,
        component="turn",
        qid=question_id,
        seq=sequence,
        text=question_text[:80],
    )


def turn_destroy(turn_id: str, session_id: str, reason: str = "") -> None:
    _log(
        "TURN_DESTROY",
        session_id=session_id,
        turn_id=turn_id,
        component="turn",
        reason=reason,
    )


def turn_advance(
    session_id: str, turn_id: str, from_index: int, to_index: int
) -> None:
    _log(
        "TURN_ADVANCE",
        session_id=session_id,
        turn_id=turn_id,
        component="turn",
        src=from_index,
        dst=to_index,
    )


def turn_retry(
    session_id: str, turn_id: str, index: int, retries: int
) -> None:
    _log(
        "TURN_RETRY",
        session_id=session_id,
        turn_id=turn_id,
        component="turn",
        index=index,
        retries=retries,
    )


# ── Question presentation ──


def question_ask(
    session_id: str,
    turn_id: str,
    question_id: str,
    sequence: int,
    text: str,
) -> None:
    _log(
        "QUESTION_ASK",
        session_id=session_id,
        turn_id=turn_id,
        component="question",
        qid=question_id,
        seq=sequence,
        text=text[:80],
    )


# ── Transcript processing (widTTS ownership/acceptance logic) ──


def transcript_accepted(
    session_id: str, turn_id: str, transcript_id: str, text: str
) -> None:
    _log(
        "TRANSCRIPT_ACCEPTED",
        session_id=session_id,
        turn_id=turn_id,
        component="transcript",
        transcript_id=transcript_id,
        text=text[:120],
    )


def transcript_rejected(
    session_id: str,
    turn_id: str,
    transcript_id: str = "",
    reason: str = "",
) -> None:
    _log(
        "TRANSCRIPT_REJECTED",
        session_id=session_id,
        turn_id=turn_id,
        component="transcript",
        severity="WARNING",
        transcript_id=transcript_id or "none",
        reason=reason[:80],
    )


def transcript_assigned(
    session_id: str, turn_id: str, transcript_id: str, text: str
) -> None:
    _log(
        "TRANSCRIPT_ASSIGNED",
        session_id=session_id,
        turn_id=turn_id,
        component="transcript",
        transcript_id=transcript_id,
        text=text[:120],
    )


# ── FSM transitions ──


def fsm_guard_reject(
    session_id: str, turn_id: str, current_state: str
) -> None:
    _log(
        "FSM_GUARD_REJECT",
        session_id=session_id,
        turn_id=turn_id,
        component="fsm",
        severity="WARNING",
        state=current_state,
    )


# ── Interruption classification (widTTS business logic) ──


def interrupt_detected(
    session_id: str, turn_id: str, transcript: str
) -> None:
    _log(
        "INTERRUPT_DETECTED",
        session_id=session_id,
        turn_id=turn_id,
        component="interruption",
        text=transcript[:80],
    )


def interrupt_classify_start(
    session_id: str,
    turn_id: str,
    transcript: str,
) -> None:
    _log(
        "INTERRUPT_CLASSIFY_START",
        session_id=session_id,
        turn_id=turn_id,
        component="interruption",
        text=transcript[:80],
    )


def interrupt_classify_end(
    session_id: str,
    turn_id: str,
    interrupt_type: str,
    confidence: float,
    duration_ms: int,
) -> None:
    _log(
        "INTERRUPT_CLASSIFY_END",
        session_id=session_id,
        turn_id=turn_id,
        component="interruption",
        type=interrupt_type,
        confidence=f"{confidence:.2f}",
        dur_ms=duration_ms,
    )


def interrupt_routed(
    session_id: str, turn_id: str, interrupt_type: str, action: str
) -> None:
    _log(
        "INTERRUPT_ROUTED",
        session_id=session_id,
        turn_id=turn_id,
        component="interruption",
        type=interrupt_type,
        action=action,
    )


# ── LLM pipeline (widTTS owns LLM via WidTTSLLMBridge) ──


def llm_started(session_id: str, turn_id: str) -> None:
    _log(
        "LLM_STARTED",
        session_id=session_id,
        turn_id=turn_id,
        component="llm",
    )


def llm_first_token(
    session_id: str, turn_id: str, token_index: int = 0
) -> None:
    _log(
        "LLM_FIRST_TOKEN",
        session_id=session_id,
        turn_id=turn_id,
        component="llm",
        idx=token_index,
    )


def llm_completed(
    session_id: str,
    turn_id: str,
    duration_ms: int,
    token_count: int,
    classification: str = "",
    should_advance: bool = False,
) -> None:
    kwargs = {
        "component": "llm",
        "dur_ms": duration_ms,
        "tokens": token_count,
    }
    if classification:
        kwargs["classification"] = classification
    if should_advance is not None:
        kwargs["advance"] = should_advance
    _log("LLM_COMPLETED", session_id=session_id, turn_id=turn_id, **kwargs)


def llm_cancelled(session_id: str, turn_id: str, reason: str) -> None:
    _log(
        "LLM_CANCELLED",
        session_id=session_id,
        turn_id=turn_id,
        component="llm",
        severity="WARNING",
        reason=reason[:80],
    )


def llm_error(session_id: str, turn_id: str, error: str) -> None:
    _log(
        "LLM_ERROR",
        session_id=session_id,
        turn_id=turn_id,
        component="llm",
        severity="ERROR",
        error=error[:200],
    )


# ── Validation pipeline (widTTS business) ──


def validation_start(
    session_id: str, turn_id: str, question_id: str, transcript: str
) -> None:
    _log(
        "VALIDATION_START",
        session_id=session_id,
        turn_id=turn_id,
        component="validation",
        qid=question_id,
        text=transcript[:80],
    )


def validation_end(
    session_id: str,
    turn_id: str,
    should_advance: bool,
    duration_ms: int,
    reason: str,
) -> None:
    _log(
        "VALIDATION_END",
        session_id=session_id,
        turn_id=turn_id,
        component="validation",
        advance=should_advance,
        dur_ms=duration_ms,
        reason=reason[:80],
    )


def validation_cancelled(
    session_id: str, turn_id: str, reason: str
) -> None:
    _log(
        "VALIDATION_CANCELLED",
        session_id=session_id,
        turn_id=turn_id,
        component="validation",
        severity="WARNING",
        reason=reason[:80],
    )


def validation_discarded(
    session_id: str, turn_id: str, bound_turn_id: str
) -> None:
    _log(
        "VALIDATION_DISCARDED",
        session_id=session_id,
        turn_id=turn_id,
        component="validation",
        severity="WARNING",
        bound_turn=bound_turn_id,
    )


# ── Correction (widTTS business) ──


def correction_received(
    session_id: str, turn_id: str, new_text: str
) -> None:
    _log(
        "CORRECTION_RECEIVED",
        session_id=session_id,
        turn_id=turn_id,
        component="correction",
        text=new_text[:80],
    )


def correction_applied(
    session_id: str,
    turn_id: str,
    old_text: str,
    new_text: str,
    stack_depth: int,
) -> None:
    _log(
        "CORRECTION_APPLIED",
        session_id=session_id,
        turn_id=turn_id,
        component="correction",
        depth=stack_depth,
        old=old_text[:40],
        new=new_text[:40],
    )


# ── Error diagnostics (widTTS business) ──


def error_occurred(
    session_id: str,
    turn_id: str,
    component: str,
    operation: str,
    error: str,
    stack_trace: str = "",
) -> None:
    """Log an unexpected exception with full correlation context.

    Does NOT include API keys, credentials, or user PII.
    """
    kwargs = {
        "component": component,
        "severity": "ERROR",
        "operation": operation,
        "error": error[:200],
    }
    if stack_trace:
        kwargs["stack"] = stack_trace[:500]
    _log("ERROR", session_id=session_id, turn_id=turn_id, **kwargs)


# ── Latency metrics (widTTS business) ──


def latency_metric(
    metric_name: str,
    value_ms: int,
    session_id: str = "",
    turn_id: str = "",
    **kwargs,
) -> None:
    """Emit a structured latency measurement.

    Metric names used in this system:
        - time_to_first_llm_token
        - time_to_last_llm_token
        - time_to_validation_start
        - time_to_validation_end
        - total_response_latency
        - total_turn_latency
        - interruption_latency
    """
    _log(
        "LATENCY_METRIC",
        session_id=session_id,
        turn_id=turn_id,
        component="metrics",
        metric=metric_name,
        value_ms=value_ms,
        **kwargs,
    )


# ── Resource lifecycle (widTTS business) ──


def resource_created(
    resource_type: str, resource_id: str, session_id: str = "", turn_id: str = ""
) -> None:
    _log(
        "RESOURCE_CREATED",
        session_id=session_id,
        turn_id=turn_id,
        component="resource",
        resource_type=resource_type,
        resource_id=resource_id,
    )


def resource_destroyed(
    resource_type: str,
    resource_id: str,
    session_id: str = "",
    turn_id: str = "",
    reason: str = "",
) -> None:
    _log(
        "RESOURCE_DESTROYED",
        session_id=session_id,
        turn_id=turn_id,
        component="resource",
        resource_type=resource_type,
        resource_id=resource_id,
        reason=reason[:80],
    )
