"""
Structured Event Emitter for widTTS LiveKit sessions.

Covers SDD Extension observability requirements:
- Application Startup/Shutdown
- Room Created/Joined/Closed
- Session Started/Completed/Failed
- Plugin Created/Destroyed
- LLM/STT/TTS lifecycle events

Every event includes timestamp, session_id, and relevant metadata.
Never logs secrets.
"""

import logging
import time
from typing import Optional, Dict, Any

logger = logging.getLogger("structured_events")


def _ts() -> float:
    return time.time()


def _base(event_type: str, session_id: str = "", **extra: Any) -> Dict[str, Any]:
    """Build a structured event dict."""
    evt = {
        "event": event_type,
        "timestamp": _ts(),
        "session_id": session_id,
    }
    evt.update(extra)
    return evt


# ── Application lifecycle ────────────────────────────────────────────

def app_startup(version: str = "", db_ok: bool = False, key_version: int = 0) -> Dict[str, Any]:
    evt = _base("app_startup", version=version, db_ok=db_ok, key_version=key_version)
    logger.info("[EVENT] app_startup version=%s db_ok=%s key_version=%d", version, db_ok, key_version)
    return evt


def app_shutdown(reason: str = "normal") -> Dict[str, Any]:
    evt = _base("app_shutdown", reason=reason)
    logger.info("[EVENT] app_shutdown reason=%s", reason)
    return evt


# ── Room lifecycle ────────────────────────────────────────────────────

def room_created(session_id: str, room_name: str) -> Dict[str, Any]:
    evt = _base("room_created", session_id, room_name=room_name)
    logger.info("[EVENT] room_created session=%s room=%s", session_id, room_name)
    return evt


def room_joined(session_id: str, room_name: str) -> Dict[str, Any]:
    evt = _base("room_joined", session_id, room_name=room_name)
    logger.info("[EVENT] room_joined session=%s room=%s", session_id, room_name)
    return evt


def room_closed(session_id: str, room_name: str, reason: str = "") -> Dict[str, Any]:
    evt = _base("room_closed", session_id, room_name=room_name, reason=reason)
    logger.info("[EVENT] room_closed session=%s room=%s reason=%s", session_id, room_name, reason)
    return evt


# ── Session lifecycle ─────────────────────────────────────────────────

def session_started(session_id: str, bot_id: str, bot_name: str, conversation_type: str) -> Dict[str, Any]:
    evt = _base("session_started", session_id, bot_id=bot_id, bot_name=bot_name, conversation_type=conversation_type)
    logger.info("[EVENT] session_started session=%s bot=%s type=%s", session_id, bot_name, conversation_type)
    return evt


def session_completed(session_id: str, duration_ms: int = 0, turns: int = 0) -> Dict[str, Any]:
    evt = _base("session_completed", session_id, duration_ms=duration_ms, turns=turns)
    logger.info("[EVENT] session_completed session=%s duration_ms=%d turns=%d", session_id, duration_ms, turns)
    return evt


def session_failed(session_id: str, error: str, phase: str = "") -> Dict[str, Any]:
    evt = _base("session_failed", session_id, error=error[:200], phase=phase)
    logger.error("[EVENT] session_failed session=%s phase=%s error=%s", session_id, phase, error[:200])
    return evt


# ── Plugin lifecycle ──────────────────────────────────────────────────

def plugin_created(session_id: str, plugin_type: str, provider: str) -> Dict[str, Any]:
    evt = _base("plugin_created", session_id, plugin_type=plugin_type, provider=provider)
    logger.info("[EVENT] plugin_created session=%s type=%s provider=%s", session_id, plugin_type, provider)
    return evt


def plugin_destroyed(session_id: str, plugin_type: str) -> Dict[str, Any]:
    evt = _base("plugin_destroyed", session_id, plugin_type=plugin_type)
    logger.info("[EVENT] plugin_destroyed session=%s type=%s", session_id, plugin_type)
    return evt


def plugin_error(session_id: str, plugin_type: str, error: str) -> Dict[str, Any]:
    evt = _base("plugin_error", session_id, plugin_type=plugin_type, error=error[:200])
    logger.error("[EVENT] plugin_error session=%s type=%s error=%s", session_id, plugin_type, error[:200])
    return evt


# ── LLM lifecycle ─────────────────────────────────────────────────────

def llm_started(session_id: str, model: str) -> Dict[str, Any]:
    evt = _base("llm_started", session_id, model=model)
    logger.info("[EVENT] llm_started session=%s model=%s", session_id, model)
    return evt


def llm_first_token(session_id: str, ttft_ms: int) -> Dict[str, Any]:
    evt = _base("llm_first_token", session_id, ttft_ms=ttft_ms)
    logger.info("[EVENT] llm_first_token session=%s ttft_ms=%d", session_id, ttft_ms)
    return evt


def llm_completed(session_id: str, duration_ms: int, token_count: int, action: str = "") -> Dict[str, Any]:
    evt = _base("llm_completed", session_id, duration_ms=duration_ms, token_count=token_count, action=action)
    logger.info("[EVENT] llm_completed session=%s duration_ms=%d tokens=%d action=%s", session_id, duration_ms, token_count, action)
    return evt


def llm_error(session_id: str, error: str) -> Dict[str, Any]:
    evt = _base("llm_error", session_id, error=error[:200])
    logger.error("[EVENT] llm_error session=%s error=%s", session_id, error[:200])
    return evt


# ── STT/TTS lifecycle ─────────────────────────────────────────────────

def stt_transcript(session_id: str, text: str, is_final: bool) -> Dict[str, Any]:
    evt = _base("stt_transcript", session_id, text=text[:120], is_final=is_final)
    logger.debug("[EVENT] stt_transcript session=%s final=%s text=%s", session_id, is_final, text[:80])
    return evt


def tts_started(session_id: str, text_length: int) -> Dict[str, Any]:
    evt = _base("tts_started", session_id, text_length=text_length)
    logger.info("[EVENT] tts_started session=%s text_len=%d", session_id, text_length)
    return evt


def tts_completed(session_id: str, duration_ms: int) -> Dict[str, Any]:
    evt = _base("tts_completed", session_id, duration_ms=duration_ms)
    logger.info("[EVENT] tts_completed session=%s duration_ms=%d", session_id, duration_ms)
    return evt
