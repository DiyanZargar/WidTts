"""Structured pipeline event logger for deterministic debugging and replay.

Every major pipeline event is logged with a consistent schema:
    timestamp | event=EVENT_TYPE | session_id | turn_id | epoch |
    component=... | severity=... | details...

Required fields on every log line:
    - timestamp (ms precision)
    - event (EVENT_TYPE)
    - session_id (full UUID — no truncation)
    - turn_id (full UUID — no truncation)
    - epoch (integer, -1 if N/A)
    - component (subsystem name)
    - severity (INFO / WARNING / ERROR)

This makes it trivial to:
    1. Find where the pipeline breaks by scanning for gaps in event sequence.
    2. Correlate every log line back to a single conversation + turn.
    3. Reconstruct an entire conversation from logs alone.
    4. Query / aggregate logs with structured filters.
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
    epoch: int = -1,
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
        # conversation_id is the same concept in this codebase
        parts.append(f"conversation_id={session_id}")
    if turn_id:
        parts.append(f"turn_id={turn_id}")
    if epoch >= 0:
        parts.append(f"epoch={epoch}")
    parts.append(f"component={component}")
    parts.append(f"severity={severity}")
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    return " | ".join(parts)


def _log(
    event_type: str,
    session_id: str = "",
    turn_id: str = "",
    epoch: int = -1,
    component: str = "pipeline",
    severity: str = "INFO",
    **kwargs,
) -> None:
    """Emit a single structured pipeline log line at the appropriate level."""
    msg = f"[PIPELINE] {_ts()} | {_fmt(event_type, session_id, turn_id, epoch, component, severity, **kwargs)}"
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


# ── STT pipeline ──


def stt_connected(session_id: str, turn_id: str = "") -> None:
    _log(
        "STT_CONNECTED",
        session_id=session_id,
        turn_id=turn_id,
        component="stt",
    )


def stt_reconnect(session_id: str, turn_id: str = "", reason: str = "") -> None:
    _log(
        "STT_RECONNECT",
        session_id=session_id,
        turn_id=turn_id,
        component="stt",
        severity="WARNING",
        reason=reason[:80],
    )


def stt_audio_sent(session_id: str, bytes_count: int) -> None:
    _log(
        "STT_AUDIO_SENT",
        session_id=session_id,
        component="stt",
        bytes=bytes_count,
    )


def stt_partial_transcript(
    session_id: str, turn_id: str, epoch: int, text: str
) -> None:
    _log(
        "STT_PARTIAL",
        session_id=session_id,
        turn_id=turn_id,
        epoch=epoch,
        component="stt",
        text=text[:80],
    )


def stt_final_transcript(
    session_id: str, turn_id: str, epoch: int, text: str
) -> None:
    _log(
        "STT_FINAL",
        session_id=session_id,
        turn_id=turn_id,
        epoch=epoch,
        component="stt",
        text=text[:120],
    )


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


def stt_stale_discarded(
    session_id: str, turn_id: str, item_epoch: int, current_epoch: int
) -> None:
    _log(
        "STT_STALE_DISCARDED",
        session_id=session_id,
        turn_id=turn_id,
        component="stt",
        severity="WARNING",
        item_epoch=item_epoch,
        current_epoch=current_epoch,
    )


def stt_epoch_advance(
    session_id: str, turn_id: str, new_epoch: int
) -> None:
    _log(
        "STT_EPOCH_ADVANCE",
        session_id=session_id,
        turn_id=turn_id,
        component="stt",
        new_epoch=new_epoch,
    )


# ── Transcript processing ──


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


# ── Interruption classification ──


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
    is_tts_playing: bool,
) -> None:
    _log(
        "INTERRUPT_CLASSIFY_START",
        session_id=session_id,
        turn_id=turn_id,
        component="interruption",
        tts_playing=is_tts_playing,
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


# ── LLM pipeline ──


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


def llm_token(
    session_id: str, turn_id: str, token: str, token_index: int
) -> None:
    _log(
        "LLM_TOKEN",
        session_id=session_id,
        turn_id=turn_id,
        component="llm",
        idx=token_index,
        token=token[:40],
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


# ── Validation pipeline ──


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


# ── Correction ──


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


# ── TTS pipeline ──


def tts_connected(session_id: str, turn_id: str = "") -> None:
    _log(
        "TTS_CONNECTED",
        session_id=session_id,
        turn_id=turn_id,
        component="tts",
    )


def tts_synthesize_start(
    session_id: str, turn_id: str, text: str
) -> None:
    _log(
        "TTS_SYNTHESIZE_START",
        session_id=session_id,
        turn_id=turn_id,
        component="tts",
        text=text[:80],
    )


def tts_synthesize_end(
    session_id: str,
    turn_id: str,
    duration_ms: int,
    audio_bytes: int,
    chunk_count: int = 0,
) -> None:
    _log(
        "TTS_SYNTHESIZE_END",
        session_id=session_id,
        turn_id=turn_id,
        component="tts",
        dur_ms=duration_ms,
        bytes=audio_bytes,
        chunks=chunk_count,
    )


def tts_first_chunk(
    session_id: str, turn_id: str, chunk_size: int
) -> None:
    _log(
        "TTS_FIRST_CHUNK",
        session_id=session_id,
        turn_id=turn_id,
        component="tts",
        size=chunk_size,
    )


def tts_last_chunk(
    session_id: str, turn_id: str, chunk_size: int, total_chunks: int
) -> None:
    _log(
        "TTS_LAST_CHUNK",
        session_id=session_id,
        turn_id=turn_id,
        component="tts",
        size=chunk_size,
        total_chunks=total_chunks,
    )


def tts_send_to_client(
    session_id: str, turn_id: str, audio_bytes: int
) -> None:
    _log(
        "TTS_SEND_TO_CLIENT",
        session_id=session_id,
        turn_id=turn_id,
        component="tts",
        bytes=audio_bytes,
    )


def tts_stream_end(session_id: str, turn_id: str) -> None:
    _log(
        "TTS_STREAM_END",
        session_id=session_id,
        turn_id=turn_id,
        component="tts",
    )


def tts_cancelled(session_id: str, turn_id: str, reason: str) -> None:
    _log(
        "TTS_CANCELLED",
        session_id=session_id,
        turn_id=turn_id,
        component="tts",
        severity="WARNING",
        reason=reason[:80],
    )


# ── WebSocket events ──


def websocket_connected(
    session_id: str, client_ip: str = ""
) -> None:
    _log(
        "WEBSOCKET_CONNECTED",
        session_id=session_id,
        component="websocket",
        client=client_ip or "unknown",
    )


def websocket_disconnected(
    session_id: str, reason: str = ""
) -> None:
    _log(
        "WEBSOCKET_DISCONNECTED",
        session_id=session_id,
        component="websocket",
        reason=reason[:80],
    )


def ws_frame_received(
    session_id: str, frame_type: str, detail: str = ""
) -> None:
    _log(
        "WS_FRAME_RECEIVED",
        session_id=session_id,
        component="websocket",
        type=frame_type,
        detail=detail[:40],
    )


def ws_control_message(session_id: str, msg_type: str) -> None:
    _log(
        "WS_CONTROL_MESSAGE",
        session_id=session_id,
        component="websocket",
        type=msg_type,
    )


# ── Error diagnostics ──


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
    _log("ERROR", session_id=session_id, turn_id=turn_id, epoch=-1, **kwargs)


# ── Latency metrics ──


def latency_metric(
    metric_name: str,
    value_ms: int,
    session_id: str = "",
    turn_id: str = "",
    **kwargs,
) -> None:
    """Emit a structured latency measurement.

    Metric names used in this system:
        - time_to_first_partial_transcript
        - time_to_final_transcript
        - time_to_validation_start
        - time_to_validation_end
        - time_to_first_llm_token
        - time_to_last_llm_token
        - time_to_first_tts_chunk
        - time_to_last_tts_chunk
        - time_to_playback_start
        - time_to_playback_end
        - total_response_latency
        - total_turn_latency
        - interruption_latency
        - websocket_reconnect_latency
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


# ── Resource lifecycle ──


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


# ── Frontend pass-through (no-ops: actual logging is in JS console) ──
# These placeholders document the expected frontend events so that a
# production engineer knows browser-side events exist and should be
# correlated via session_id / turn_id if forwarded to the backend.


def fe_tts_playback_start(text: str) -> None:
    """Frontend: TTS audio playback started. Logged in browser console."""
    pass


def fe_tts_playback_end(duration_ms: int) -> None:
    """Frontend: TTS audio playback finished. Logged in browser console."""
    pass


def fe_mic_chunk_sent(bytes_count: int) -> None:
    """Frontend: Mic audio chunk sent to backend. Logged in browser console."""
    pass


def fe_vad_interrupt(text: str) -> None:
    """Frontend: VAD detected user speech during TTS. Logged in browser console."""
    pass


# ── Backward-compatible aliases ──

ws_disconnect = websocket_disconnected
ws_control_message = ws_control_message  # same name already exists
ws_frame_received = ws_frame_received  # same name already exists
