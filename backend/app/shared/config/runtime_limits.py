"""
Runtime Limits — configurable caps for all runtime resources.

Every limit is read from settings with a sane default.
Components import and query limits rather than hardcoding values.
"""
from dataclasses import dataclass
from app.shared.config.settings import settings


@dataclass(frozen=True)
class RuntimeLimits:
    # Context / conversation
    max_context_tokens: int = 4000
    max_retries_per_item: int = 3

    # Audio
    max_playback_queue_size: int = 200
    max_audio_buffer_seconds: int = 10
    sample_rate: int = 48000

    # Session
    max_session_duration_seconds: int = 3600  # 1 hour
    max_pending_tasks_per_turn: int = 10

    # Streaming
    max_concurrent_streams: int = 1
    tts_chunk_timeout_seconds: float = 30.0

    # Reconnection
    max_reconnect_attempts: int = 5
    reconnect_base_delay_ms: int = 500

    # STT
    stt_queue_max_size: int = 500
    stt_epoch_drain_timeout_ms: int = 200

    # Provider health
    provider_timeout_seconds: float = 30.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_seconds: float = 60.0

    @classmethod
    def from_settings(cls) -> "RuntimeLimits":
        return cls(
            max_context_tokens=getattr(settings, "max_context_tokens", 4000),
            max_retries_per_item=getattr(settings, "max_retries_per_item", 3),
        )


_limits: RuntimeLimits | None = None


def get_limits() -> RuntimeLimits:
    global _limits
    if _limits is None:
        _limits = RuntimeLimits.from_settings()
    return _limits
