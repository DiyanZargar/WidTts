"""Structured pipeline event logger for voice sessions.

Logs business-level events for session lifecycle and LLM pipeline.
LiveKit infrastructure events are not logged here.
"""

import time
import logging

logger = logging.getLogger("voice_platform")


def _ts() -> str:
    """Return a millisecond-precision timestamp string."""
    return (
        time.strftime("%H:%M:%S", time.localtime())
        + f".{int(time.time() * 1000) % 1000:03d}"
    )


def _log(
    event_type: str,
    session_id: str = "",
    severity: str = "INFO",
    **kwargs: object,
) -> None:
    """Emit a single structured pipeline log line."""
    parts = [f"event={event_type}"]
    if session_id:
        parts.append(f"session_id={session_id}")
    parts.append(f"severity={severity}")
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    msg = f"[PIPELINE] {_ts()} | {' | '.join(parts)}"
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
        type=conversation_type,
        recovery=is_recovery,
    )


def session_end(session_id: str, reason: str) -> None:
    _log("SESSION_END", session_id=session_id, reason=reason)


# ── LLM pipeline ──


def llm_started(session_id: str, turn_id: str) -> None:
    _log("LLM_STARTED", session_id=session_id, turn_id=turn_id)


def llm_completed(
    session_id: str,
    turn_id: str,
    duration_ms: int,
    token_count: int,
    classification: str = "",
    should_advance: bool = False,
) -> None:
    kwargs = {
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
        severity="WARNING",
        reason=reason[:80],
    )


def llm_error(session_id: str, turn_id: str, error: str) -> None:
    _log(
        "LLM_ERROR",
        session_id=session_id,
        turn_id=turn_id,
        severity="ERROR",
        error=error[:200],
    )
