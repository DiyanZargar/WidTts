"""
Central Tuning Knobs for Voice, VAD, Interruption, and Speech Pipelines.

All sensitivity thresholds, turn-taking timing, noise-resistance parameters,
provider defaults, and audio configuration are managed in this single module.

Design Principles:
1. Pure configuration & typed dataclasses — no business logic.
2. Every parameter has a battle-tested recommended default.
3. If an environment variable is present, it automatically overrides the default.
4. If an environment variable is omitted or removed, the recommended default takes over.
5. Parameters expected from the UI (e.g. Bot Name, Prompts, Voice ID) are NOT in the env,
   and UI/Snapshot values strictly override defaults at runtime.
6. Rich docstrings on every property provide full parameter descriptions and impact
   when hovering in IDEs (VS Code / Pyright).
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Set, Tuple


# ── Environment Variable Helpers ─────────────────────────────────────

def _get_str(key: str, default: str) -> str:
    """Retrieve string from environment or fallback to default."""
    val = os.getenv(key)
    return val if val is not None and val != "" else default


def _get_float(key: str, default: float) -> float:
    """Retrieve float from environment or fallback to default."""
    val = os.getenv(key)
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _get_int(key: str, default: int) -> int:
    """Retrieve integer from environment or fallback to default."""
    val = os.getenv(key)
    if val is None or val == "":
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _get_bool(key: str, default: bool) -> bool:
    """Retrieve boolean from environment (1/true/yes) or fallback to default."""
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _get_tuple_floats(key_min: str, key_max: str, default: Optional[Tuple[float, float]]) -> Optional[Tuple[float, float]]:
    """Retrieve float tuple from two environment keys or fallback to default."""
    vmin = os.getenv(key_min)
    vmax = os.getenv(key_max)
    if vmin is not None and vmax is not None and vmin != "" and vmax != "":
        try:
            return (float(vmin), float(vmax))
        except (ValueError, TypeError):
            pass
    return default


def _get_list_str(key: str, default: List[str]) -> List[str]:
    """Retrieve comma-separated string list from environment or fallback to default."""
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return [item.strip() for item in val.split(",") if item.strip()]


def _get_set_str(key: str, default: Set[str]) -> Set[str]:
    """Retrieve comma-separated string set from environment or fallback to default."""
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return {item.strip().lower() for item in val.split(",") if item.strip()}


# ── Section 3: Voice Activity Detection (Silero VAD) ─────────────────

@dataclass
class VADKnobs:
    """
    Silero Voice Activity Detection (VAD) Tuning Knobs.
    
    Controls the neural network acoustic filter before sound is treated as speech.
    """
    min_speech_duration: float = field(default_factory=lambda: _get_float("VAD_MIN_SPEECH_DURATION", 0.05))
    """
    Minimum continuous speech duration (seconds) required before declaring voice start.
    
    • Lower: Faster speech trigger (more responsive to short utterances like 'yes' / 'no')
    • Higher: Filters out acoustic pops, microphone handling noise, and short clicks
    • Recommended: 0.05 – 0.10s
    • Env override: VAD_MIN_SPEECH_DURATION
    """

    activation_threshold: float = field(default_factory=lambda: _get_float("VAD_ACTIVATION_THRESHOLD", 0.40))
    """
    Neural network confidence probability (0.0 to 1.0) required to trigger speech.
    
    • Lower: More sensitive, triggers in noisy environments or with soft speakers
    • Higher: Stricter, requires louder/clearer speech
    • Recommended: 0.40 – 0.55
    • Env override: VAD_ACTIVATION_THRESHOLD
    """

    deactivation_threshold: float = field(default_factory=lambda: _get_float("VAD_DEACTIVATION_THRESHOLD", 0.30))
    """
    Confidence threshold below which speech is considered officially ended (hysteresis floor).
    
    • Recommended: 0.30 – 0.40 (should remain 0.10 below activation_threshold)
    • Env override: VAD_DEACTIVATION_THRESHOLD
    """

    min_silence_duration: float = field(default_factory=lambda: _get_float("VAD_MIN_SILENCE_DURATION", 0.30))
    """
    Silence duration (seconds) required before VAD signals that the user has stopped speaking.
    
    • Original: 0.40s (400ms)
    • Env override: VAD_MIN_SILENCE_DURATION
    """

    prefix_padding_duration: float = field(default_factory=lambda: _get_float("VAD_PREFIX_PADDING_DURATION", 0.30))
    """
    Audio buffer retained (seconds) BEFORE the speech trigger point.
    
    • Env override: VAD_PREFIX_PADDING_DURATION
    """

    max_buffered_speech: float = field(default_factory=lambda: _get_float("VAD_MAX_BUFFERED_SPEECH", 60.0))
    """
    Safety ceiling (seconds) for buffered audio before forcing a frame flush to prevent memory leaks.
    
    • Env override: VAD_MAX_BUFFERED_SPEECH
    """

    sample_rate: int = field(default_factory=lambda: _get_int("VAD_SAMPLE_RATE", 16000))
    """
    Audio sample rate in Hz for Silero ONNX inference (16000 standard).
    
    • Env override: VAD_SAMPLE_RATE
    """

    force_cpu: bool = field(default_factory=lambda: _get_bool("VAD_FORCE_CPU", True))
    """
    Forces Silero ONNX model to run on CPU (<1ms execution, zero GPU VRAM overhead).
    
    • Env override: VAD_FORCE_CPU
    """


# ── Section 4: Turn-Taking & Interruption (Barge-In) ──────────────────

@dataclass
class InterruptionKnobs:
    """
    Turn-Taking Interruption and Barge-In Knobs.
    
    Controls how the AI detects, validates, and recovers from interruptions.
    """
    enabled: bool = field(default_factory=lambda: _get_bool("INTERRUPTION_ENABLED", True))
    """
    Master toggle for barge-in capability (allowing user to interrupt agent speech).
    
    • Env override: INTERRUPTION_ENABLED
    """

    mode: Literal["adaptive", "vad"] = field(default_factory=lambda: _get_str("INTERRUPTION_MODE", "vad"))  # type: ignore
    """
    Interruption intelligence mode:
    • 'vad': Local ONNX VAD barge-in on CPU (fast, reliable, zero cloud dependency).
    • 'adaptive': Cloud-managed barge-in (requires LiveKit Cloud subscription).
    • Env override: INTERRUPTION_MODE
    """

    min_duration: float = field(default_factory=lambda: _get_float("INTERRUPTION_MIN_DURATION", 1.0))
    """
    Minimum continuous user speaking time (seconds) required before interrupting the agent.
    
    • Recommended: 1.0s (stricter VAD filter against coughs and breaths)
    • Env override: INTERRUPTION_MIN_DURATION
    """

    min_words: int = field(default_factory=lambda: _get_int("INTERRUPTION_MIN_WORDS", 1))
    """
    Minimum recognized STT words required before confirming an interruption (1 = must have real speech).
    
    • Recommended: 1
    • Env override: INTERRUPTION_MIN_WORDS
    """

    resume_false_interruption: bool = field(default_factory=lambda: _get_bool("INTERRUPTION_RESUME_FALSE_INTERRUPTION", True))
    """
    If True, when a loud noise momentarily pauses TTS but no user words follow within the timeout,
    the agent automatically RESUMES speaking the rest of its sentence.
    
    • Env override: INTERRUPTION_RESUME_FALSE_INTERRUPTION
    """

    false_interruption_timeout: float = field(default_factory=lambda: _get_float("INTERRUPTION_FALSE_TIMEOUT", 1.0))
    """
    Time window (seconds) to wait for STT words before declaring an interruption a false alarm and resuming playback.
    
    • Env override: INTERRUPTION_FALSE_TIMEOUT
    """

    backchannel_boundary: Optional[Tuple[float, float]] = field(
        default_factory=lambda: _get_tuple_floats("INTERRUPTION_BACKCHANNEL_MIN", "INTERRUPTION_BACKCHANNEL_MAX", (0.5, 1.5))
    )
    """
    Time window (min, max seconds) for short backchannels ('uh-huh', 'yeah', 'mhm').
    If user speech fits in this window and ends, the agent ignores it and keeps speaking.
    
    • Env override: INTERRUPTION_BACKCHANNEL_MIN, INTERRUPTION_BACKCHANNEL_MAX
    """

    discard_audio_if_uninterruptible: bool = field(default_factory=lambda: _get_bool("INTERRUPTION_DISCARD_IF_UNINTERRUPTIBLE", True))
    """
    Discards user audio spoken during uninterruptible speech (e.g. farewell) to prevent queuing delayed responses.
    
    • Env override: INTERRUPTION_DISCARD_IF_UNINTERRUPTIBLE
    """


# ── Section 5: Endpointing (End-of-Turn Timing) ───────────────────────

@dataclass
class EndpointingKnobs:
    """
    End-of-Turn Silence and Response Timing Knobs.
    
    Controls how long the agent waits after the user stops speaking before responding.
    """
    mode: Literal["fixed", "dynamic"] = field(default_factory=lambda: _get_str("ENDPOINTING_MODE", "dynamic"))  # type: ignore
    """
    Endpointing calculation mode:
    • 'dynamic': Adapts delay based on sentence structure & STT punctuation.
    • 'fixed': Uses a static timer.
    • Env override: ENDPOINTING_MODE
    """

    min_delay: float = field(default_factory=lambda: _get_float("ENDPOINTING_MIN_DELAY", 0.70))
    """
    Minimum response delay (seconds) after user stops speaking.
    
    • Recommended: 0.70s
    • Env override: ENDPOINTING_MIN_DELAY
    """

    max_delay: float = field(default_factory=lambda: _get_float("ENDPOINTING_MAX_DELAY", 3.0))
    """
    Maximum wait time (seconds) when user pauses mid-sentence before responding.
    
    • Recommended: 3.0s
    • Env override: ENDPOINTING_MAX_DELAY
    """

    alpha: float = field(default_factory=lambda: _get_float("ENDPOINTING_ALPHA", 0.90))
    """
    Smoothing factor for dynamic endpointing calculation.
    
    • Original: 0.90
    • Env override: ENDPOINTING_ALPHA
    """


# ── Section 6: Preemptive Generation & Turn Limits ───────────────────

@dataclass
class PreemptiveGenerationKnobs:
    """
    Speculative LLM and TTS Generation Knobs.
    
    Reduces end-to-end latency by anticipating the end of the user's turn.
    """
    enabled: bool = field(default_factory=lambda: _get_bool("PREEMPTIVE_GENERATION_ENABLED", True))
    """
    Starts speculative LLM generation while the user is finishing their sentence (saves ~200-400ms).
    
    • Env override: PREEMPTIVE_GENERATION_ENABLED
    """

    preemptive_tts: bool = field(default_factory=lambda: _get_bool("PREEMPTIVE_TTS_ENABLED", False))
    """
    Starts TTS synthesis on speculative tokens. Kept False to avoid unnecessary TTS billing on aborted turns.
    
    • Env override: PREEMPTIVE_TTS_ENABLED
    """

    max_speech_duration: float = field(default_factory=lambda: _get_float("PREEMPTIVE_MAX_SPEECH_DURATION", 10.0))
    """
    Max speech duration (seconds) for speculative generation before resetting.
    
    • Env override: PREEMPTIVE_MAX_SPEECH_DURATION
    """

    max_retries: int = field(default_factory=lambda: _get_int("PREEMPTIVE_MAX_RETRIES", 3))
    """
    Retry attempts on speculative generation failures.
    
    • Env override: PREEMPTIVE_MAX_RETRIES
    """


@dataclass
class UserTurnLimitKnobs:
    """
    Safety limits on continuous user speech without agent response.
    """
    max_words: Optional[int] = field(default_factory=lambda: None if not os.getenv("USER_TURN_LIMIT_MAX_WORDS") else _get_int("USER_TURN_LIMIT_MAX_WORDS", 150))
    """
    Max accumulated words before forcing a turn response (None = disabled).
    
    • Env override: USER_TURN_LIMIT_MAX_WORDS
    """

    max_duration: Optional[float] = field(default_factory=lambda: None if not os.getenv("USER_TURN_LIMIT_MAX_DURATION") else _get_float("USER_TURN_LIMIT_MAX_DURATION", 30.0))
    """
    Max speech duration (seconds) before forcing a turn response (None = disabled).
    
    • Env override: USER_TURN_LIMIT_MAX_DURATION
    """


# ── Section 7: AgentSession Core Runtime, Delays & Lifecycle ─────────

@dataclass
class AgentRuntimeKnobs:
    """
    Core LiveKit AgentSession Runtime Knobs.
    """
    aec_warmup_duration: float = field(default_factory=lambda: _get_float("AEC_WARMUP_DURATION", 1.0))
    """
    Grace period (seconds) after agent starts speaking during which interruptions are ignored.
    
    • Recommended: 2.5s
    • Why it matters: Prevents speaker-to-mic bleed from self-interrupting the agent while WebRTC AEC calibrates.
    • Env override: AEC_WARMUP_DURATION
    """

    user_away_timeout: float = field(default_factory=lambda: _get_float("ROOM_INACTIVITY_TIMEOUT_SECONDS", 15.0))
    """
    Mutual silence timeout (seconds) before marking user 'away' and triggering farewell disconnect.
    
    • Recommended: 15.0s (unified with ROOM_INACTIVITY_TIMEOUT_SECONDS)
    • Env override: ROOM_INACTIVITY_TIMEOUT_SECONDS
    """

    transcription_timeout: Optional[float] = field(default_factory=lambda: _get_float("TRANSCRIPTION_TIMEOUT", 2.0))
    """
    Timeout (seconds) to fire user_transcription_timeout if VAD heard audio but STT got no words.
    
    • Recommended: 3.0s
    • Env override: TRANSCRIPTION_TIMEOUT
    """

    session_close_transcript_timeout: float = field(default_factory=lambda: _get_float("SESSION_CLOSE_TRANSCRIPT_TIMEOUT", 2.0))
    """
    Seconds to wait for final STT tokens when tearing down the session.
    
    • Env override: SESSION_CLOSE_TRANSCRIPT_TIMEOUT
    """

    min_consecutive_speech_delay: float = field(default_factory=lambda: _get_float("MIN_CONSECUTIVE_SPEECH_DELAY", 0.05))
    """
    Minimum pause (seconds) between back-to-back agent speech turns.
    
    • Env override: MIN_CONSECUTIVE_SPEECH_DELAY
    """

    max_tool_steps: int = field(default_factory=lambda: _get_int("MAX_TOOL_STEPS", 3))
    """
    Max consecutive tool invocations per turn.
    
    • Env override: MAX_TOOL_STEPS
    """

    use_tts_aligned_transcript: bool = field(default_factory=lambda: _get_bool("USE_TTS_ALIGNED_TRANSCRIPT", False))
    """
    Syncs transcript events with exact TTS audio playback timestamps (keep False unless TTS provides word timestamps).
    
    • Env override: USE_TTS_ALIGNED_TRANSCRIPT
    """

    tts_text_transforms: List[str] = field(default_factory=lambda: _get_list_str("TTS_TEXT_TRANSFORMS", ["filter_markdown", "filter_emoji"]))
    """
    Text transformations applied before TTS synthesis to strip markdown and emojis.
    
    • Env override: TTS_TEXT_TRANSFORMS
    """

    expressive: bool = field(default_factory=lambda: _get_bool("EXPRESSIVE_TTS", False))
    """
    Injects expressive emotional markup tags into LLM prompt for expressive TTS models.
    
    • Env override: EXPRESSIVE_TTS
    """

    ivr_detection: bool = field(default_factory=lambda: _get_bool("IVR_DETECTION", False))
    """
    Detects automated IVR phone menus and DTMF beeps.
    
    • Env override: IVR_DETECTION
    """

    greeting_stabilization_delay: float = field(default_factory=lambda: _get_float("GREETING_STABILIZATION_DELAY", 0.3))
    """
    Sleep pause (seconds) before sending the greeting to ensure the WebRTC track is fully negotiated.
    
    • Env override: GREETING_STABILIZATION_DELAY
    """

    farewell_drain_delay: float = field(default_factory=lambda: _get_float("FAREWELL_DRAIN_DELAY", 4.0))
    """
    Sleep pause (seconds) to allow farewell TTS audio to finish playing on user speakers before disconnecting.
    
    • Env override: FAREWELL_DRAIN_DELAY
    """

    farewell_publish_delay: float = field(default_factory=lambda: _get_float("FAREWELL_PUBLISH_DELAY", 0.5))
    """
    Brief pause (seconds) after publishing session_end data packet before tearing down WebRTC session.
    
    • Env override: FAREWELL_PUBLISH_DELAY
    """


# ── Section 8: Speech-to-Text (STT) Providers ────────────────────────

@dataclass
class DeepgramSTTKnobs:
    """
    Deepgram Speech-to-Text (STT) Plugin Knobs.
    
    Note: Model, language, and API keys come dynamically from the UI / bot snapshot.
    """
    default_model: str = "nova-3"
    default_language: str = "en-US"

    interim_results: bool = field(default_factory=lambda: _get_bool("STT_INTERIM_RESULTS", True))
    """
    Streams non-final partial words in real-time for instant word-based barge-in.
    
    • Env override: STT_INTERIM_RESULTS
    """

    punctuate: bool = field(default_factory=lambda: _get_bool("STT_PUNCTUATE", True))
    """
    Adds punctuation (periods, commas) to transcript. Critical for dynamic endpointing.
    
    • Env override: STT_PUNCTUATE
    """

    smart_format: bool = field(default_factory=lambda: _get_bool("STT_SMART_FORMAT", True))
    """
    Converts numbers, dates, currency into readable format ($50 vs fifty dollars).
    
    • Env override: STT_SMART_FORMAT
    """

    endpointing_ms: int = field(default_factory=lambda: _get_int("DEEPGRAM_ENDPOINTING_MS", 300))
    """
    Deepgram silence duration (ms) before finalizing an utterance. 400ms was the original working default.
    
    • Env override: DEEPGRAM_ENDPOINTING_MS
    """

    filler_words: bool = field(default_factory=lambda: _get_bool("STT_FILLER_WORDS", True))
    """
    Transcribes filler words ('um', 'uh') so the turn detector knows the user is hesitating.
    
    • Env override: STT_FILLER_WORDS
    """

    no_delay: bool = field(default_factory=lambda: _get_bool("STT_NO_DELAY", True))
    """
    Emits interim words immediately without waiting for sequence buffers.
    
    • Env override: STT_NO_DELAY
    """

    vad_events: bool = field(default_factory=lambda: _get_bool("STT_VAD_EVENTS", True))
    """
    Enables Deepgram-side VAD events over WebSocket.
    
    • Env override: STT_VAD_EVENTS
    """

    sample_rate: int = field(default_factory=lambda: _get_int("STT_SAMPLE_RATE", 16000))
    """
    STT input audio sample rate in Hz.
    
    • Env override: STT_SAMPLE_RATE
    """

    profanity_filter: bool = field(default_factory=lambda: _get_bool("STT_PROFANITY_FILTER", False))
    """
    Masks profane words with asterisks.
    
    • Env override: STT_PROFANITY_FILTER
    """

    redact: Optional[str] = field(default_factory=lambda: os.getenv("STT_REDACT") or None)
    """
    Redacts sensitive data ('pci', 'ssn', 'numbers').
    
    • Env override: STT_REDACT
    """


@dataclass
class ElevenLabsSTTKnobs:
    """
    ElevenLabs Speech-to-Text (STT) Plugin Knobs.
    """
    default_model_id: str = "scribe_v1"
    default_language: str = ""


# ── Section 9: Text-to-Speech (TTS) Providers ────────────────────────

@dataclass
class ElevenLabsTTSKnobs:
    """
    ElevenLabs Text-to-Speech (TTS) Plugin Knobs.
    
    Note: Voice ID, custom model, and language come dynamically from the UI / bot snapshot.
    """
    default_model: str = "eleven_turbo_v2_5"
    default_voice_id: str = "EXAVITQu4vr4xnSDxMaL"

    auto_mode: bool = field(default_factory=lambda: _get_bool("TTS_AUTO_MODE", True))
    """
    Synthesizes sentence-by-sentence for lowest time-to-first-audio.
    
    • Env override: TTS_AUTO_MODE
    """

    apply_text_normalization: Literal["auto", "off", "on"] = field(default_factory=lambda: _get_str("TTS_APPLY_TEXT_NORMALIZATION", "auto"))  # type: ignore
    """
    Controls text normalization ('auto', 'on', 'off') for spelling out numbers and abbreviations.
    
    • Env override: TTS_APPLY_TEXT_NORMALIZATION
    """

    inactivity_timeout: int = field(default_factory=lambda: _get_int("TTS_INACTIVITY_TIMEOUT", 180))
    """
    WebSocket connection keepalive timeout in seconds.
    
    • Env override: TTS_INACTIVITY_TIMEOUT
    """

    stability: float = field(default_factory=lambda: _get_float("TTS_VOICE_STABILITY", 0.55))
    """
    Voice stability (0.0 to 1.0). Higher = more consistent tone.
    
    • Env override: TTS_VOICE_STABILITY
    """

    similarity_boost: float = field(default_factory=lambda: _get_float("TTS_VOICE_SIMILARITY_BOOST", 0.80))
    """
    Voice similarity boost (0.0 to 1.0). Closeness to original sample.
    
    • Env override: TTS_VOICE_SIMILARITY_BOOST
    """

    style: float = field(default_factory=lambda: _get_float("TTS_VOICE_STYLE", 0.0))
    """
    Style exaggeration (0.0 to 1.0). Kept at 0.0 for optimal latency.
    
    • Env override: TTS_VOICE_STYLE
    """

    speed: float = field(default_factory=lambda: _get_float("TTS_VOICE_SPEED", 1.0))
    """
    Voice speech rate multiplier (0.5 to 2.0).
    
    • Env override: TTS_VOICE_SPEED
    """

    use_speaker_boost: bool = field(default_factory=lambda: _get_bool("TTS_VOICE_USE_SPEAKER_BOOST", True))
    """
    Enhances clarity of the speaker.
    
    • Env override: TTS_VOICE_USE_SPEAKER_BOOST
    """


@dataclass
class DeepgramTTSKnobs:
    """
    Deepgram Aura Text-to-Speech (TTS) Plugin Knobs.
    """
    default_model: str = "aura-asteria-en"
    sample_rate: int = field(default_factory=lambda: _get_int("DEEPGRAM_TTS_SAMPLE_RATE", 24000))
    encoding: str = field(default_factory=lambda: _get_str("DEEPGRAM_TTS_ENCODING", "linear16"))


@dataclass
class FishAudioTTSKnobs:
    """
    Fish Audio Text-to-Speech (TTS) Adapter Knobs.
    """
    default_model: str = "s2.1-pro"
    sample_rate: int = field(default_factory=lambda: _get_int("FISH_AUDIO_SAMPLE_RATE", 24000))
    num_channels: int = field(default_factory=lambda: _get_int("FISH_AUDIO_NUM_CHANNELS", 1))
    connect_timeout_seconds: int = field(default_factory=lambda: _get_int("FISH_AUDIO_CONNECT_TIMEOUT", 15))
    total_timeout_seconds: int = field(default_factory=lambda: _get_int("FISH_AUDIO_TOTAL_TIMEOUT", 30))


# ── Section 10: LiveKit Room & WebRTC Room Configuration ─────────────

@dataclass
class RoomOptionsKnobs:
    """
    LiveKit Room & WebRTC Track Publishing Knobs.
    """
    sync_transcription: bool = field(default_factory=lambda: _get_bool("ROOM_SYNC_TRANSCRIPTION", False))
    """
    Publishes text transcripts immediately without waiting for TTS audio timestamps.
    
    • Env override: ROOM_SYNC_TRANSCRIPTION
    """

    transcription_speed_factor: float = field(default_factory=lambda: _get_float("ROOM_TRANSCRIPTION_SPEED_FACTOR", 1.0))
    """
    Speed multiplier when synchronizing text output.
    
    • Env override: ROOM_TRANSCRIPTION_SPEED_FACTOR
    """

    json_format: bool = field(default_factory=lambda: _get_bool("ROOM_TEXT_JSON_FORMAT", False))
    """
    Formats text output events as raw JSON payloads.
    
    • Env override: ROOM_TEXT_JSON_FORMAT
    """

    audio_output_sample_rate: int = field(default_factory=lambda: _get_int("ROOM_AUDIO_OUTPUT_SAMPLE_RATE", 24000))
    """
    WebRTC audio track publishing sample rate in Hz (24000 standard for Opus voice).
    
    • Env override: ROOM_AUDIO_OUTPUT_SAMPLE_RATE
    """

    audio_output_num_channels: int = field(default_factory=lambda: _get_int("ROOM_AUDIO_OUTPUT_NUM_CHANNELS", 1))
    """
    Audio track publishing channel count (1 = mono).
    
    • Env override: ROOM_AUDIO_OUTPUT_NUM_CHANNELS
    """

    audio_output_track_name: str = field(default_factory=lambda: _get_str("ROOM_AUDIO_TRACK_NAME", "agent_audio"))
    """
    Published WebRTC audio track name.
    
    • Env override: ROOM_AUDIO_TRACK_NAME
    """

    audio_input_auto_gain_control: bool = field(default_factory=lambda: _get_bool("ROOM_AUDIO_INPUT_AUTO_GAIN_CONTROL", True))
    """
    Ingest automatic gain control on the server side.
    
    • Env override: ROOM_AUDIO_INPUT_AUTO_GAIN_CONTROL
    """

    audio_input_pre_connect_audio: bool = field(default_factory=lambda: _get_bool("ROOM_PRE_CONNECT_AUDIO", True))
    """
    Buffers audio during WebRTC handshake so early user words are not lost.
    
    • Env override: ROOM_PRE_CONNECT_AUDIO
    """

    audio_input_pre_connect_audio_timeout: float = field(default_factory=lambda: _get_float("ROOM_PRE_CONNECT_AUDIO_TIMEOUT", 3.0))
    """
    Timeout window (seconds) for early pre-connect audio buffer.
    
    • Env override: ROOM_PRE_CONNECT_AUDIO_TIMEOUT
    """

    close_on_disconnect: bool = field(default_factory=lambda: _get_bool("ROOM_CLOSE_ON_DISCONNECT", True))
    """
    Closes backend agent session when participant disconnects.
    
    • Env override: ROOM_CLOSE_ON_DISCONNECT
    """

    delete_room_on_close: bool = field(default_factory=lambda: _get_bool("ROOM_DELETE_ON_CLOSE", False))
    """
    Deletes LiveKit room on session termination.
    
    • Env override: ROOM_DELETE_ON_CLOSE
    """

    room_token_ttl_seconds: int = field(default_factory=lambda: _get_int("LIVEKIT_TOKEN_TTL_SECONDS", 3600))
    """
    Participant room token TTL in seconds (1 hour).
    
    • Env override: LIVEKIT_TOKEN_TTL_SECONDS
    """

    agent_token_ttl_seconds: int = field(default_factory=lambda: _get_int("AGENT_TOKEN_TTL_SECONDS", 7200))
    """
    Agent worker token TTL in seconds (2 hours).
    
    • Env override: AGENT_TOKEN_TTL_SECONDS
    """

    room_inactivity_timeout_seconds: float = field(default_factory=lambda: _get_float("ROOM_INACTIVITY_TIMEOUT_SECONDS", 15.0))
    """
    Room inactivity cleanup timeout in seconds (15 seconds).
    
    • Env override: ROOM_INACTIVITY_TIMEOUT_SECONDS
    """


# ── Section 11: LLM Bridge & Deterministic Conversation Policy ───────

@dataclass
class LLMBridgeKnobs:
    """
    LLM Bridge and Conversational Generation Knobs.
    
    Note: Model, system prompt, bot name, and API keys come dynamically from the UI / bot snapshot.
    """
    default_model: str = "gpt-4o-mini"
    temperature: float = field(default_factory=lambda: _get_float("LLM_TEMPERATURE", 0.7))
    top_p: float = field(default_factory=lambda: _get_float("LLM_TOP_P", 1.0))
    max_tokens: int = field(default_factory=lambda: _get_int("LLM_MAX_TOKENS", 1024))
    stream: bool = field(default_factory=lambda: _get_bool("LLM_STREAM", True))

    error_fallback_text: str = field(default_factory=lambda: _get_str("LLM_ERROR_FALLBACK_TEXT", "I'm sorry, I had trouble generating a response. Could you try again?"))
    stop_ack_text: str = field(default_factory=lambda: _get_str("POLICY_STOP_ACK_TEXT", "Alright, I'll pause here. Just say 'continue' when you're ready."))
    end_ack_text: str = field(default_factory=lambda: _get_str("POLICY_END_ACK_TEXT", "Thanks for chatting! Goodbye."))
    repeat_fallback_text: str = field(default_factory=lambda: _get_str("POLICY_REPEAT_FALLBACK_TEXT", "I don't have a previous response to repeat."))
    farewell_marker: str = field(default_factory=lambda: _get_str("FAREWELL_MARKER", "[END_SESSION]"))
    default_farewell_speech: str = field(default_factory=lambda: _get_str("FAREWELL_SPEECH", "It was nice talking with you. Goodbye!"))


@dataclass
class ConversationPolicyKnobs:
    """
    Deterministic System Commands for instant zero-LLM response routing.
    """
    stop_commands: Set[str] = field(default_factory=lambda: _get_set_str("POLICY_STOP_COMMANDS", {
        "stop", "stop talking", "be quiet", "shut up", "pause", "quiet"
    }))
    end_commands: Set[str] = field(default_factory=lambda: _get_set_str("POLICY_END_COMMANDS", {
        "end", "end conversation", "start over", "reset", "quit", "i'm done", "goodbye"
    }))
    repeat_commands: Set[str] = field(default_factory=lambda: _get_set_str("POLICY_REPEAT_COMMANDS", {
        "repeat", "say that again", "what did you say", "pardon"
    }))
    continue_commands: Set[str] = field(default_factory=lambda: _get_set_str("POLICY_CONTINUE_COMMANDS", {
        "continue", "go on", "proceed", "keep going"
    }))
    forget_commands: Set[str] = field(default_factory=lambda: _get_set_str("POLICY_FORGET_COMMANDS", {
        "forget that", "never mind", "disregard", "ignore that"
    }))
    urgent_interruption_words: Set[str] = field(default_factory=lambda: _get_set_str("POLICY_URGENT_INTERRUPTION_WORDS", {
        "wait", "stop", "no", "no no", "no, no", "hold on", "hang on", "pause",
        "one sec", "one second", "wait a second", "wait a minute", "shut up", "be quiet", "stop talking"
    }))


# ── Section 12: Frontend WebRTC Microphone Capture & Constraints ─────

@dataclass
class FrontendAudioCaptureKnobs:
    """
    WebRTC Client Audio Constraints (Browser Microphone Capture).
    """
    echo_cancellation: bool = field(default_factory=lambda: _get_bool("FRONTEND_ECHO_CANCELLATION", True))
    """
    Browser hardware/software Acoustic Echo Cancellation (AEC). Prevents speaker feedback.
    
    • Env override: FRONTEND_ECHO_CANCELLATION
    """

    noise_suppression: bool = field(default_factory=lambda: _get_bool("FRONTEND_NOISE_SUPPRESSION", True))
    """
    Browser background noise filter (air conditioning, fan hums).
    
    • Env override: FRONTEND_NOISE_SUPPRESSION
    """

    auto_gain_control: bool = field(default_factory=lambda: _get_bool("FRONTEND_AUTO_GAIN_CONTROL", True))
    """
    Automatic gain control for microphone level normalization.
    
    • Env override: FRONTEND_AUTO_GAIN_CONTROL
    """

    sample_rate: int = field(default_factory=lambda: _get_int("FRONTEND_SAMPLE_RATE", 48000))
    """
    WebRTC capture rate in Hz (48kHz standard browser audio rate).
    
    • Env override: FRONTEND_SAMPLE_RATE
    """

    channel_count: int = field(default_factory=lambda: _get_int("FRONTEND_CHANNEL_COUNT", 1))
    """
    Mono microphone input.
    
    • Env override: FRONTEND_CHANNEL_COUNT
    """


# ── Section 13: Outbound HTTP & Admin Network Timeouts ───────────────

@dataclass
class NetworkTimeoutKnobs:
    """
    Outbound HTTP & Admin Network Timeouts in Seconds.
    """
    health_check_timeout: float = field(default_factory=lambda: _get_float("HTTP_HEALTH_CHECK_TIMEOUT", 3.0))
    """
    Quick health check probe timeout in seconds.
    
    • Env override: HTTP_HEALTH_CHECK_TIMEOUT
    """

    provider_verify_timeout: float = field(default_factory=lambda: _get_float("HTTP_PROVIDER_VERIFY_TIMEOUT", 8.0))
    """
    Verification timeout when testing user API keys.
    
    • Env override: HTTP_PROVIDER_VERIFY_TIMEOUT
    """

    model_fetch_timeout: float = field(default_factory=lambda: _get_float("HTTP_MODEL_FETCH_TIMEOUT", 10.0))
    """
    Timeout when fetching remote voice/model lists from ElevenLabs/Deepgram.
    
    • Env override: HTTP_MODEL_FETCH_TIMEOUT
    """


# ── Master Voice Platform Knobs ──────────────────────────────────────

@dataclass
class VoicePlatformKnobs:
    """
    Master Registry uniting all subsystem knobs into a single source of truth.
    """
    vad: VADKnobs = field(default_factory=VADKnobs)
    interruption: InterruptionKnobs = field(default_factory=InterruptionKnobs)
    endpointing: EndpointingKnobs = field(default_factory=EndpointingKnobs)
    preemptive: PreemptiveGenerationKnobs = field(default_factory=PreemptiveGenerationKnobs)
    turn_limit: UserTurnLimitKnobs = field(default_factory=UserTurnLimitKnobs)
    runtime: AgentRuntimeKnobs = field(default_factory=AgentRuntimeKnobs)
    deepgram_stt: DeepgramSTTKnobs = field(default_factory=DeepgramSTTKnobs)
    elevenlabs_stt: ElevenLabsSTTKnobs = field(default_factory=ElevenLabsSTTKnobs)
    elevenlabs_tts: ElevenLabsTTSKnobs = field(default_factory=ElevenLabsTTSKnobs)
    deepgram_tts: DeepgramTTSKnobs = field(default_factory=DeepgramTTSKnobs)
    fish_audio_tts: FishAudioTTSKnobs = field(default_factory=FishAudioTTSKnobs)
    llm: LLMBridgeKnobs = field(default_factory=LLMBridgeKnobs)
    policy: ConversationPolicyKnobs = field(default_factory=ConversationPolicyKnobs)
    room: RoomOptionsKnobs = field(default_factory=RoomOptionsKnobs)
    frontend_audio: FrontendAudioCaptureKnobs = field(default_factory=FrontendAudioCaptureKnobs)
    network: NetworkTimeoutKnobs = field(default_factory=NetworkTimeoutKnobs)

    def to_turn_handling_dict(self) -> Dict[str, Any]:
        """Convert turn handling knobs into the exact dictionary shape expected by LiveKit AgentSession."""
        return {
            "endpointing": {
                "mode": self.endpointing.mode,
                "min_delay": self.endpointing.min_delay,
                "max_delay": self.endpointing.max_delay,
                "alpha": self.endpointing.alpha,
            },
            "interruption": {
                "enabled": self.interruption.enabled,
                "mode": self.interruption.mode,
                "min_duration": self.interruption.min_duration,
                "min_words": self.interruption.min_words,
                "resume_false_interruption": self.interruption.resume_false_interruption,
                "false_interruption_timeout": self.interruption.false_interruption_timeout,
                "backchannel_boundary": self.interruption.backchannel_boundary,
                "discard_audio_if_uninterruptible": self.interruption.discard_audio_if_uninterruptible,
            },
            "preemptive_generation": {
                "enabled": self.preemptive.enabled,
                "preemptive_tts": self.preemptive.preemptive_tts,
                "max_speech_duration": self.preemptive.max_speech_duration,
                "max_retries": self.preemptive.max_retries,
            },
            "user_turn_limit": {
                "max_words": self.turn_limit.max_words,
                "max_duration": self.turn_limit.max_duration,
            },
        }

    def to_silero_vad_kwargs(self) -> Dict[str, Any]:
        """Convert VAD knobs into kwargs for silero.VAD.load(...)."""
        return {
            "min_speech_duration": self.vad.min_speech_duration,
            "min_silence_duration": self.vad.min_silence_duration,
            "prefix_padding_duration": self.vad.prefix_padding_duration,
            "max_buffered_speech": self.vad.max_buffered_speech,
            "activation_threshold": self.vad.activation_threshold,
            "deactivation_threshold": self.vad.deactivation_threshold,
            "sample_rate": self.vad.sample_rate,
            "force_cpu": self.vad.force_cpu,
        }


# Global singleton instance for platform-wide import
knobs = VoicePlatformKnobs()
