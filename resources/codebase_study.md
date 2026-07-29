# Codebase Study Guide
## Build the Voice Conversational Platform from Scratch

Welcome! This study guide will take you step-by-step through the **entire implementation** of the Real-Time Voice Conversational Platform.

This guide is structured as a chronological, dependency-ordered blueprint. As you build or review each file, you will understand **what** was done, **why** it was done, **how** the functions connect, and **where** each piece fits into the overall architecture.

---

# ARCHITECTURAL OVERVIEW

The application is built using **Clean Architecture** and a **Modular Monolith** pattern:

```
                  ┌────────────────────────────────────────┐
                  │          Presentation Layer            │
                  │  FastAPI WebSockets / HTTP / SPA Serve  │
                  └──────────────────┬─────────────────────┘
                                     │
                  ┌──────────────────▼─────────────────────┐
                  │           Application Layer            │
                  │  Use Cases, Services, Coordinators     │
                  └──────────────────┬─────────────────────┘
                                     │
                  ┌──────────────────▼─────────────────────┐
                  │             Domain Layer               │
                  │ Entities, Interfaces, FSM, TurnContext  │
                  │ Policy, Value Objects                   │
                  └──────────────────▲─────────────────────┘
                                     │
                  ┌──────────────────┴─────────────────────┐
                  │          Infrastructure Layer          │
                  │ SQLite DB, Deepgram STT/TTS, LiteLLM   │
                  │ LLM Adapters, JSON Conversation Repo   │
                  └────────────────────────────────────────┘

                  ┌────────────────────────────────────────┐
                  │        Shared Cross-Cutting Layer      │
                  │ EventBus, CancellationToken, Pipeline   │
                  │ Logger, ErrorClassifier, RuntimeLimits  │
                  │ ProviderHealth, CapabilityRegistry,     │
                  │ SessionResourceManager                  │
                  └────────────────────────────────────────┘
```

## Bounded Contexts

| Module | Domain | Application | Infrastructure |
|---|---|---|---|
| **session** | SessionEntity, SessionRepositoryInterface | CreateSession, GetSession, UpdatePointer, PauseSession, CloseSession, RuntimeStateManager | SqliteSessionRepository |
| **message** | MessageEntity, MessageRepositoryInterface | AddMessage, GetMessages | SqliteMessageRepository |
| **conversation** | ConversationFSM, TurnContext, ConversationPolicy, ValidationProviderInterface, ResponseRepositoryInterface | ConversationEngine, ResponseCoordinator, ContextManager, TaskRouter, ValidateResponse, RecordResponse | JsonConversationRepository, LiteLLMValidationAdapter, SqliteResponseRepository |
| **voice** | STTProviderInterface, TTSProviderInterface | SynthesizeSpeech | DeepgramSTTAdapter, DeepgramTTSAdapter |
| **interruption** | InterruptionEntity, InterruptionRepositoryInterface | ClassifyInterruption, RecordInterruption | SqliteInterruptionRepository, InterruptionClassifierAdapter |

---

# PART 1: Shared Core & Infrastructure Foundations

Before writing any business logic, we must lay down the shared configuration, logging, domain exception boundaries, security cryptography, database connections, and migration systems.

---

## LESSON 01: Core Environment & Settings Configuration

### Files:
- `backend/requirements.txt`
- `backend/.env.example` & `backend/.env`
- `backend/app/shared/config/settings.py`

### 1. Requirements (`backend/requirements.txt`)
We define our backend Python dependencies:
- `fastapi` & `uvicorn[standard]`: High-performance asynchronous WebSockets and HTTP server.
- `pydantic` & `pydantic-settings`: Type validation and environment variable parsing.
- `python-dotenv`: Loading `.env` key-value pairs into environment variables.
- `websockets`: Low-level WebSocket client library for streaming audio to Deepgram STT.
- `httpx`: Asynchronous HTTP client for Deepgram TTS REST fallback.
- `litellm`: Unified client wrapper for LLM calls (e.g. Gemini via OpenAI-compatible endpoints).
- `pytest` & `pytest-asyncio`: Automated test runner and async test support.

### 2. Environment Variables (`backend/.env`)
Contains API keys and service configurations:
```env
DEEPGRAM_API_KEY=...
DEEPGRAM_TTS_MODEL=aura-2-thalia-en
DEEPGRAM_STT_URL=wss://api.deepgram.com/v1/listen?punctuate=true&interim_results=true&endpointing=300

OPENAI_API_KEY=...
OPENAI_BASE_URL=https://llm.app.emlylabs.com/v1
AI_VALIDATION_MODEL=openai/gemini/gemini-2.0-flash-lite

DATABASE_PATH=app.db
MAX_RETRIES_PER_ITEM=3
CONVERSATION_DEFINITIONS_DIR=app/conversation_definitions
```

> **Note**: `endpointing=300` (not `1000`). The 300ms endpointing provides faster turn detection for natural voice conversation.

### 3. Settings Singleton (`backend/app/shared/config/settings.py`)
```python
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    deepgram_api_key: str
    deepgram_tts_model: str
    deepgram_stt_url: str
    
    openai_api_key: str
    openai_base_url: str
    ai_validation_model: str
    
    database_path: str = "app.db"
    max_retries_per_item: int = 3
    conversation_definitions_dir: str = os.path.join("app", "conversation_definitions")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

#### Why was this done?
- **Pydantic `BaseSettings`**: Automatically loads `.env` variables and raises a strict `ValidationError` at startup if required API keys are missing.
- **`settings` Singleton**: Avoids re-parsing `.env` across different modules.

---

## LESSON 02: Unified Logger Initialization

### File:
`backend/app/shared/logging/logger.py`

```python
import logging

logger = logging.getLogger("conversation_widget")
logging.basicConfig(level=logging.INFO)
```

#### Why was this done?
Provides a single named logger (`"conversation_widget"`) so all application logs follow a uniform namespace and log level.

---

## LESSON 03: Structured Pipeline Logger

### File:
`backend/app/shared/logging/pipeline_logger.py`

A structured event logger for deterministic debugging and replay. Every major pipeline event is logged with a consistent schema:

```
timestamp | event=EVENT_TYPE | session_id | turn_id | epoch | component=... | severity=... | details...
```

Provides 50+ structured logging functions covering:
- **Session lifecycle**: `session_start`, `session_end`
- **Conversation lifecycle**: `conversation_start`, `conversation_end`
- **Turn lifecycle**: `turn_create`, `turn_destroy`, `turn_advance`, `turn_retry`
- **STT pipeline**: `stt_connected`, `stt_reconnect`, `stt_audio_sent`, `stt_partial_transcript`, `stt_final_transcript`, `stt_epoch_advance`, `stt_stale_discarded`
- **Transcript processing**: `transcript_assigned`, `transcript_accepted`, `transcript_rejected`
- **Validation**: `validation_start`, `validation_end`, `validation_cancelled`, `validation_discarded`
- **LLM pipeline**: `llm_started`, `llm_first_token`, `llm_token`, `llm_completed`, `llm_cancelled`
- **TTS pipeline**: `tts_connected`, `tts_synthesize_start`, `tts_synthesize_end`, `tts_first_chunk`, `tts_send_to_client`, `tts_stream_end`, `tts_cancelled`
- **Interruption**: `interrupt_detected`, `interrupt_classify_start`, `interrupt_classify_end`, `interrupt_routed`
- **Correction**: `correction_received`, `correction_applied`
- **WebSocket**: `websocket_connected`, `websocket_disconnected`, `ws_frame_received`, `ws_control_message`
- **Errors**: `error_occurred` (with full correlation context, no PII)
- **Latency metrics**: `latency_metric` (supports 14 named metrics from TTFPT to total_turn_latency)
- **Resource lifecycle**: `resource_created`, `resource_destroyed`
- **Frontend placeholders**: `fe_tts_playback_start`, `fe_vad_interrupt` (documentation-only, actual logging in browser console)

#### Why was this done?
- **Deterministic debugging**: Every log line includes full session_id/turn_id/epoch so a single grep on a UUID returns every related log line.
- **Gap detection**: Scanning for gaps in event sequence reveals where the pipeline breaks.
- **Conversation reconstruction**: An entire conversation can be reconstructed from logs alone.
- **Structured filtering**: Logs can be queried and aggregated with structured filters.

---

## LESSON 04: Domain Exception Boundaries

### File:
`backend/app/shared/exceptions/domain_exceptions.py`

```python
class DomainError(Exception):
    """Base exception for all domain errors."""
    pass

class ConversationTypeNotFoundError(DomainError):
    pass

class SessionNotFoundError(DomainError):
    pass

class InvalidConversationSchemaError(DomainError):
    pass

class DuplicateConversationIdError(DomainError):
    pass
```

#### Why was this done?
Clean Architecture rule: The domain layer must not depend on HTTP/WebSocket framework exceptions. Custom exception classes allow presentation controllers to catch errors and format appropriate error responses.

---

## LESSON 05: Error Classification Framework

### File:
`backend/app/shared/errors/error_classifier.py`

Classifies errors into structured categories with deterministic recovery strategies:

- **`ErrorCategory`**: `RECOVERABLE`, `FATAL`, `USER_ERROR`
- **`ErrorSeverity`**: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`
- **`RecoveryAction`**: `RETRY`, `RECONNECT`, `RESTART_SESSION`, `NOTIFY_USER`, `NONE`

Known error patterns mapped to classifications:
| Pattern | Category | Recovery | Retryable | Max Retries |
|---|---|---|---|---|
| `timeout` | RECOVERABLE | RETRY | Yes | 3 |
| `connection_lost` | RECOVERABLE | RECONNECT | Yes | 5 |
| `provider_unavailable` | RECOVERABLE | RECONNECT | Yes | 3 |
| `queue_overflow` | RECOVERABLE | RETRY | Yes | 1 |
| `unsupported_browser` | FATAL | NOTIFY_USER | No | 0 |
| `microphone_unavailable` | FATAL | NOTIFY_USER | No | 0 |
| `invalid_session` | FATAL | RESTART_SESSION | No | 0 |
| `permission_denied` | USER_ERROR | NOTIFY_USER | No | 0 |
| `network_offline` | USER_ERROR | RECONNECT | Yes | 10 |

#### Why was this done?
Deterministic error handling replaces scattered try/catch logic. Every error produces a `ClassifiedError` dataclass with structured fields (retryable, max_retries, retry_delay_ms, notify_frontend, cleanup_required) so the WebSocket handler can make consistent recovery decisions.

---

## LESSON 06: Runtime Limits Configuration

### File:
`backend/app/shared/config/runtime_limits.py`

A frozen dataclass providing configurable caps for all runtime resources. Components import and query limits instead of hardcoding values:

```python
@dataclass(frozen=True)
class RuntimeLimits:
    max_context_tokens: int = 4000
    max_retries_per_item: int = 3
    max_playback_queue_size: int = 200
    max_audio_buffer_seconds: int = 10
    sample_rate: int = 48000
    max_session_duration_seconds: int = 3600
    max_pending_tasks_per_turn: int = 10
    max_concurrent_streams: int = 1
    tts_chunk_timeout_seconds: float = 30.0
    max_reconnect_attempts: int = 5
    reconnect_base_delay_ms: int = 500
    stt_queue_max_size: int = 500
    stt_epoch_drain_timeout_ms: int = 200
    provider_timeout_seconds: float = 30.0
    circuit_breaker_threshold: int = 5
    circuit_breaker_reset_seconds: float = 60.0
```

Singleton accessor: `get_limits()` → `RuntimeLimits` instance (lazy-initialized from settings).

---

## LESSON 07: Session Token Cryptography & Authentication

### File:
`backend/app/shared/security/token_service.py`

```python
SECRET_KEY = "conversational_platform_secure_secret_key"

def create_token(user_id: str, expires_in_seconds: int = 86400) -> str:
    # HMAC-SHA256 signed stateless token with user_id + expiration

def verify_token(token: Optional[str]) -> str:
    # Returns user_id or "user_default_guest" for unauthenticated access
    # Supports test tokens (test_user_*) for development
```

#### Why was this done?
- **HMAC-SHA256 Signing**: Generates stateless, secure tokens without needing a token store table.
- **`hmac.compare_digest`**: Prevents timing attack vulnerabilities.
- **Guest and Test Fallbacks**: Allows unauthenticated guest usage and simple test tokens.

---

## LESSON 08: EventBus — Internal Async Event Dispatcher

### File:
`backend/app/shared/events/event_bus.py`

A lightweight internal async event dispatcher — no external infrastructure (Redis/Kafka) required.

```python
@dataclass(frozen=True)
class Event:
    name: str
    payload: Any
    session_id: str = ""

class EventBus:
    def subscribe(self, event_name: str, handler: Callable) -> None
    def subscribe_async(self, event_name: str, handler: Callable) -> None
    def unsubscribe(self, event_name: str, handler) -> None
    async def publish(self, event: Event) -> None
    async def publish_raw(self, name: str, payload: Any, session_id: str = "") -> None
```

Supports both sync and async handlers. Events used in the system:
- `tts_audio_chunk` → forwards audio bytes to WebSocket client
- `tts_audio_meta` → sends metadata JSON to client
- `tts_stream_end` → signals stream completion to client
- `llm_stream_started` / `llm_stream_completed` → tracks LLM lifecycle

#### Why was this done?
Reduces coupling between the ResponseCoordinator (LLM→TTS pipeline) and the WebSocket handler (client delivery). The coordinator publishes audio chunks to the bus; the handler subscribes and forwards to the client. This makes each component independently testable.

---

## LESSON 09: CancellationToken — Unified Cancellation Framework

### File:
`backend/app/shared/cancellation/cancellation_token.py`

A single token propagates cancellation to STT, LLM, TTS, playback, pending tasks, streaming pipelines, and event listeners.

```python
class CancellationToken:
    @property
    def is_cancelled(self) -> bool
    def cancel(self, reason: str = "cancelled") -> None   # Idempotent
    def on_cancel(self, callback: Callable) -> None
    def on_cancel_async(self, callback) -> None
    async def wait(self, timeout: Optional[float] = None) -> bool
    def check(self) -> None  # Raises CancelledError if cancelled
    def child(self) -> "CancellationToken"  # Hierarchical cancellation

class CancellationTokenSource:
    @property
    def token(self) -> CancellationToken
    def cancel(self, reason: str = "cancelled") -> None
    def create_child(self) -> CancellationToken
```

#### Why was this done?
Previously, cancellation was scattered across individual component flags. The CancellationToken provides a single mechanism that the WebSocket handler creates at session start, injects into the ResponseCoordinator, and cancels on `tts_interrupt` or session end. Child tokens allow sub-components (e.g., a single TTS stream) to have scoped cancellation that propagates upward.

---

## LESSON 10: Capability Registry — Centralized Feature Detection

### File:
`backend/app/shared/capabilities/capability_registry.py`

Tracks which features are available at runtime. Components query capabilities instead of using scattered feature checks.

```python
class CapabilityRegistry:
    def register(self, name: str, available: bool = True, version: str = "", **details) -> None
    def is_available(self, name: str) -> bool
    def list_available(self) -> Set[str]
    def snapshot(self) -> Dict[str, bool]
```

Registered capabilities at startup:
| Capability | Available | Version |
|---|---|---|
| `streaming_stt` | ✅ | deepgram-sdk-7.6.0 |
| `streaming_tts` | ✅ | deepgram-sdk-7.6.0 |
| `rnnoise` | ❌ | — |
| `browser_dsp` | ✅ | — |
| `silero_vad` | ✅ | @ricky0123/vad-web |
| `barge_in` | ✅ | — |
| `audio_metrics` | ✅ | — |
| `audio_health_monitor` | ✅ | — |
| `runtime_diagnostics` | ✅ | — |

---

## LESSON 11: Provider Health Manager — Circuit Breaker & Latency Tracking

### File:
`backend/app/shared/providers/provider_health_manager.py`

Monitors provider health with a circuit breaker pattern and exponential moving average latency tracking.

```python
class CircuitState(str, Enum):
    CLOSED = "closed"        # Normal operation
    OPEN = "open"            # Provider is failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery

class ProviderHealthManager:
    def register(self, name: str) -> None
    def record_success(self, name: str, latency_ms: float = 0.0) -> None
    def record_failure(self, name: str, error: str = "") -> None
    def is_available(self, name: str) -> bool
    def get_stats(self, name: str) -> Dict[str, Any]
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]
```

Registered providers: `deepgram_stt`, `deepgram_tts`, `litellm`.

Circuit breaker opens after `circuit_breaker_threshold` (default 5) consecutive failures and resets after `circuit_breaker_reset_seconds` (default 60s) in HALF_OPEN state.

#### Why was this done?
Prevents cascading failures. If the LLM provider goes down, the circuit breaker opens and subsequent calls fail fast instead of waiting for 12-second timeouts. After the reset period, one probe request tests recovery.

---

## LESSON 12: Session Resource Manager — Deterministic Resource Lifecycle

### File:
`backend/app/shared/resources/session_resource_manager.py`

When a session ends, ALL resources are released in one place. No resource cleanup is distributed across unrelated components.

```python
class SessionResourceManager:
    def __init__(self, session_id: str)
    def track_task(self, task: asyncio.Task) -> None
    def track_timer(self, handle: asyncio.TimerHandle) -> None
    def register_resource(self, name: str, resource: Any, cleanup: Optional[Callable] = None) -> None
    def register_websocket(self, ws) -> None
    def register_stt_stream(self, stream) -> None
    def register_tts_stream(self, stream) -> None
    def register_event_subscription(self, unsubscribe_fn: Callable) -> None
    async def release_all(self) -> None  # Releases everything deterministically
    def snapshot(self) -> Dict[str, Any]
```

`release_all()` cancels all tasks (with `asyncio.gather`), cancels timers, disconnects worklets, closes audio context, closes STT/TTS streams, unsubscribes event listeners, clears playback buffers, and runs custom cleanup callbacks.

---

# PART 2: Persistence & Migrations

---

## LESSON 13: Database Connection Manager

### File:
`backend/app/shared/database/db.py`

```python
import sqlite3
from contextlib import contextmanager
from app.shared.config.settings import settings

@contextmanager
def get_connection():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
```

---

## LESSON 14–18: SQL Schema Migrations

### Files:
`backend/app/shared/database/migrations/`
- `0001_create_sessions_table.sql`: `sessions` table (`session_id`, `user_id`, `start_time`, `end_time`, `conversation_type`, `status`, `current_question_index`, `current_state`, `retries`).
- `0002_create_messages_table.sql`: `messages` table (`id`, `session_id`, `sender` ['system'|'user'], `text`, `timestamp`).
- `0003_create_responses_table.sql`: `responses` table (`response_id`, `session_id`, `sequence`, `user_response`, `validation_result` ['valid'|'invalid']).
- `0004_create_interruptions_table.sql`: `interruptions` table (`interruption_id`, `session_id`, `interruption_type` ['stop'|'cancel'|'repeat'|'correction'|'end_conversation'], `interruption_text`, `timestamp`).
- `0005_add_status_index_to_sessions.sql`: Index `idx_sessions_status` on `sessions(status)`.

---

## LESSON 19–20: Migration Execution Engine & Init Hook

### Files:
- `backend/app/shared/database/migrations/runner.py`
- `backend/app/shared/database/init_db.py`

Idempotent migration runner that tracks applied files in `schema_migrations` table and executes SQL files in alphabetical order.

---

# PART 3: Shared Schemas & Domain Constants

---

## LESSON 21–25: Schemas and System Constants

### Files:
- `backend/app/shared/schemas/conversation_schema.py`: `QuestionDefinition` and `ConversationDefinitionSchema`.
- `backend/app/shared/constants/conversation_types.py`: Allowed pack IDs (`daily_life_companion`, `career_life_advisor`, `health_wellness_assistant`, `travel_planner`).
- `backend/app/shared/constants/states.py`: Allowed FSM states (`welcoming`, `asking`, `listening`, `validating`, `speaking`, `repeating`, `paused`, `completed`, `cancelled`).
- `backend/app/shared/constants/interruption_types.py`: Interruption types (`stop`, `cancel`, `repeat`, `correction`, `end_conversation`).

---

# PART 4: Session Bounded Context

---

## LESSON 26–32: Session Domain, Persistence & Use Cases

### Files:
- Entity: `backend/app/modules/session/domain/entities/session_entity.py`
- Interface: `backend/app/modules/session/domain/interfaces/session_repository_interface.py`
- Repository: `backend/app/modules/session/infrastructure/persistence/sqlite_session_repository.py`
- Use Cases: `create_session.py`, `get_session.py`, `update_pointer.py`, `pause_session.py`, `close_session.py`
- Service: `backend/app/modules/session/application/services/runtime_state_manager.py`

### RuntimeStateManager

Single source of truth for all runtime session state. Previously this state was scattered across ConnectionManager, TurnContext, audioVolumeTracker, and inline variables in conversation_handler.

```python
class ConnectionState(str, Enum):    # CONNECTING, CONNECTED, DISCONNECTED, RECONNECTING
class PlaybackState(str, Enum):      # IDLE, PLAYING, PAUSED, INTERRUPTED
class STTState(str, Enum):           # DISCONNECTED, CONNECTING, LISTENING, PROCESSING
class TTSState(str, Enum):           # DISCONNECTED, CONNECTING, SYNTHESIZING, STREAMING

@dataclass
class SessionRuntimeState:
    session_id: str
    conversation_type: str
    user_id: str
    connection_state: ConnectionState
    current_turn_id: Optional[str]
    current_question_index: int
    retry_count: int
    playback_state: PlaybackState
    current_tts_text: str
    tts_chunks_received: int
    tts_bytes_received: int
    stt_state: STTState
    tts_state: TTSState
    listening_epoch: int
    is_recovery: bool
    is_destroyed: bool

class RuntimeStateManager:
    def create_session(...) -> SessionRuntimeState
    def get_session(session_id) -> Optional[SessionRuntimeState]
    def destroy_session(session_id) -> None
    def set_connection_state(session_id, state) -> None
    def set_turn(session_id, turn_id, question_index) -> None
    def increment_retry(session_id) -> int
    def advance_question(session_id) -> int
    def set_playback_state(session_id, state, tts_text) -> None
    def record_tts_chunk(session_id, chunk_bytes) -> None
    def set_stt_state(session_id, state) -> None
    def set_tts_state(session_id, state) -> None
    def advance_epoch(session_id) -> int
    def snapshot(session_id) -> Dict[str, Any]
```

#### Why was this done?
Consolidates all runtime state into one manager with atomic transitions and read-only snapshots. Other components query the snapshot instead of reaching into each other's internals.

---

# PART 5: Message Bounded Context

---

## LESSON 33–37: Message Domain, Persistence & Use Cases

### Files:
- Entity: `backend/app/modules/message/domain/entities/message_entity.py`
- Interface: `backend/app/modules/message/domain/interfaces/message_repository_interface.py`
- Repository: `backend/app/modules/message/infrastructure/persistence/sqlite_message_repository.py`
- Use Cases: `add_message.py`, `get_messages.py`.

#### Transcript Logging & Recovery:
- `AddMessage`: Appends user or system speech to the database with ISO UTC timestamps.
- `GetMessages`: Queries messages ordered by `id ASC` to reconstruct historical context when a disconnected client reconnects to an active session.

---

# PART 6: Conversation Core & Validation Bounded Context

This is the core engine of the system containing state machine logic, turn transaction contexts, LLM validation adapters, and conversation definition packs.

---

## LESSON 38: Turn Finite State Machine (FSM)

### File:
`backend/app/modules/conversation/domain/models/conversation_fsm.py`

```python
class ConversationState(str, Enum):
    IDLE = "IDLE"
    ASKING = "ASKING"
    WAITING_FOR_TTS = "WAITING_FOR_TTS"
    TTS_PLAYING = "TTS_PLAYING"
    LISTENING = "LISTENING"
    TRANSCRIBING = "TRANSCRIBING"
    VALIDATING = "VALIDATING"
    RETRY = "RETRY"
    ADVANCE = "ADVANCE"
    NEXT_TURN = "NEXT_TURN"

ALLOWED_TRANSITIONS = {
    IDLE:           {ASKING},
    ASKING:         {WAITING_FOR_TTS},
    WAITING_FOR_TTS: {TTS_PLAYING},
    TTS_PLAYING:    {LISTENING},
    LISTENING:      {TRANSCRIBING, ASKING, TTS_PLAYING},
    TRANSCRIBING:   {VALIDATING, LISTENING},
    VALIDATING:     {ADVANCE, RETRY},
    RETRY:          {ASKING, LISTENING, TTS_PLAYING},
    ADVANCE:        {NEXT_TURN},
    NEXT_TURN:      {ASKING},
}
```

Key differences from old version:
- **Added `TTS_PLAYING`**: Explicit state for when audio is being sent to the client. Allows barge-in detection (user speaks during TTS → classify as interruption).
- **Removed `FOLLOW_UP`**: Follow-up logic handled within RETRY state.
- **Removed `COMPLETED`**: Session completion is handled at the session level, not within the turn FSM.
- **History tracking**: Every transition records `(state, timestamp, reason)` for debugging.

---

## LESSON 39: Transactional Turn Context & Race Condition Shielding

### File:
`backend/app/modules/conversation/domain/models/turn_context.py`

Significantly expanded from the original version:

```python
class TranscriptLifecycle(str, Enum):
    CREATED = "CREATED"      # Transcript object instantiated
    QUEUED = "QUEUED"        # In STT adapter queue
    ASSIGNED = "ASSIGNED"    # Bound to a TurnContext
    VALIDATED = "VALIDATED"  # Passed through LLM validation
    CONSUMED = "CONSUMED"    # Applied to conversation state
    DISCARDED = "DISCARDED"  # Rejected (late, stale, ownership fail)
    DESTROYED = "DESTROYED"  # TurnContext destroyed

class TurnContext:
    # ── Ownership verification ──
    def is_event_valid(self, turn_id, question_id, session_id) -> bool

    # ── Listening window ──
    def mark_listening_started(self) -> None
    def can_accept_transcript(self, transcript_received_at) -> bool

    # ── Transcript lifecycle ──
    def add_partial_transcript(self, text) -> None     # B10: dedup consecutive, B9: cap at 50
    def set_final_transcript(self, text) -> str         # Returns transcript_id
    def mark_transcript_consumed(self) -> None          # Single-consumption enforcement
    def mark_transcript_discarded(self, reason) -> None

    # ── Correction tracking ──
    def apply_correction(self, new_transcript) -> None  # Pushes old answer to correction_stack

    # ── Task management ──
    def register_task(self, task) -> None
    def cancel_all_tasks(self) -> int
    def cancel_active_validation(self) -> bool
    def cancel_active_llm(self) -> bool

    # ── Destruction ──
    def destroy(self) -> None
```

Key additions:
- **`TranscriptLifecycle` enum**: Every transcript follows a deterministic lifecycle: `CREATED → QUEUED → ASSIGNED → VALIDATED → CONSUMED → DESTROYED`.
- **`correction_stack`**: When the user corrects a previous answer, the old answer is archived on the stack (audit trail) and replaced.
- **`active_llm_task`**: Tracks the in-flight streaming LLM task so it can be cancelled on interruption.
- **`listening_epoch`**: Correlates with the STT adapter's epoch counter to discard stale transcripts from previous turns.
- **`listening_started_at` / `can_accept_transcript()`**: Rejects transcripts that arrived before the turn started listening.
- **Partial transcripts**: Now stored as `List[Dict[str, Any]]` with timestamps, capped at 50, with consecutive duplicate deduplication.

---

## LESSON 40: Conversation Policy — Centralized Behavioral Rules

### File:
`backend/app/modules/conversation/domain/policy/conversation_policy.py`

Centralizes all conversational behavior rules. The Conversation Engine asks: "Given this classification, what should we do?"

```python
class PolicyAction(str, Enum):
    STOP = "stop"
    REPEAT = "repeat"
    CONTINUE = "continue"
    FORGET = "forget"
    CORRECTION = "correction"
    ANSWER = "answer"
    END_CONVERSATION = "end_conversation"
    NONE = "none"

class ConversationPolicy:
    def resolve_action(self, classification_type: str, transcript: str,
                       current_retry_count: int = 0) -> Dict[str, Any]
    def evaluate_retry(self, current_retry_count: int,
                       validation_passed: bool) -> Dict[str, Any]
```

**Two-phase resolution:**
1. **Deterministic routing** (bypasses classification): Exact string matches for system commands — `stop`, `end`, `repeat`, `continue`, `forget` commands.
2. **Classification-based routing**: Maps LLM classification types (`STOP`, `END_CONVERSATION`, `REPEAT`, `CORRECTION`, `ANSWER`) to `PolicyAction`.

**Retry evaluation**: Returns `ADVANCE` if validation passed, `RETRY` if under max retries, or auto-advances if max retries exceeded.

---

## LESSON 41–43: Dynamic Conversation JSON Repository

### Files:
- Interface: `backend/app/modules/conversation/domain/interfaces/conversation_repository_interface.py`
- Implementation: `backend/app/modules/conversation/infrastructure/external/json_conversation_repository.py`
- Packs: `backend/app/conversation_definitions/` (`daily_life.json`, `career_life.json`, `health_wellness.json`, `travel_planner.json`).

Zero hardcoding — conversation scripts live entirely in JSON files. All packs loaded and validated against `ConversationDefinitionSchema` at startup.

---

## LESSON 44: Validation Provider Interface

### File:
`backend/app/modules/conversation/domain/interfaces/validation_provider_interface.py`

```python
class ValidationProviderInterface(ABC):
    @abstractmethod
    async def validate(self, item_type, item_text, expected_context, user_response) -> Dict[str, Any]:
        """Blocking full-response validation (backward compatible)."""

    @abstractmethod
    async def validate_stream(self, item_type, item_text, expected_context, user_response) -> AsyncGenerator:
        """Streaming validation yielding natural-language tokens + JSON metadata."""
```

The streaming interface is the primary path. Tokens are yielded as they arrive from the LLM; after the spoken feedback text, a `###METADATA###` delimiter separates the JSON block.

---

## LESSON 45: Response Repository Interface & Implementation

### Files:
- `backend/app/modules/conversation/domain/interfaces/response_repository_interface.py`
- `backend/app/modules/conversation/infrastructure/persistence/sqlite_response_repository.py`

```python
class ResponseRepositoryInterface(ABC):
    def add(self, sequence: int, session_id: str, user_response: str, validation_result: str) -> None

class SqliteResponseRepository(ResponseRepositoryInterface):
    def add(self, sequence, session_id, user_response, validation_result):
        # INSERT INTO responses (sequence, session_id, user_response, validation_result)
```

---

## LESSON 46–48: LLM Validation Adapter

### File:
`backend/app/modules/conversation/infrastructure/external/litellm_validation_adapter.py`

Implements `ValidationProviderInterface` with two paths:

**`validate()` (blocking)** — Three-layer architecture:
1. **Layer 1 — Deterministic Guards** (<1ms): Empty response filter, single-letter audio filter, dangling sentence detector (`DANGLING_ENDINGS` — conjunctions, carrier phrases, incomplete verbs).
2. **Layer 2 — LLM Semantic Validation**: Delegates ALL semantic reasoning to the LLM. No keyword matching, digit lists, color lists, or heuristics. Supports `reasoning_content` from DeepSeek models (checks `msg.content`, then `msg.reasoning_content`, then `msg.model_extra`, then `msg.provider_specific_fields`).
3. **Layer 3 — Graceful Degradation**: When LLM is unreachable, multi-word responses pass (accept and advance), single-word responses request clarification.

**`validate_stream()` (streaming)** — Primary path:
- Streams LLM tokens via `stream=True`, yielding `delta.content` tokens as they arrive.
- Tracks `reasoning_content` chunks separately (for models that think before responding).
- On timeout/error, emits a safe fallback token + metadata block so the caller doesn't hang.
- Hard asyncio timeout of 30s guarantees cancellation.

**Key changes from old version:**
- Removed ALL fast-path heuristics (binary yes/no, colors, complete statements).
- Added streaming validation (`validate_stream`).
- Added `reasoning_content` support for DeepSeek-style models.
- Added graceful degradation instead of hard failure.

---

## LESSON 49–51: Conversation Engine Service

### File:
`backend/app/modules/conversation/application/services/conversation_engine.py`

```python
class ConversationEngine:
    def load_script(self, conversation_type) -> Dict[str, Any]
    def get_intro_line(self, conversation_type) -> str           # NEW: intro line from JSON
    def get_current(self, conversation_type, index) -> Optional[Dict[str, Any]]
    def is_complete(self, conversation_type, index) -> bool
    def generate_human_transition(self, prev_item, user_transcript) -> str  # Enhanced
```

`generate_human_transition()` now handles name extraction ("Nice to meet you, Alex!") and richer acknowledgment patterns.

---

## LESSON 52: Context Manager — Conversation History & Token Budget

### File:
`backend/app/modules/conversation/application/services/context_manager.py`

Manages conversation history, token budget, and prompt construction for LLM calls.

```python
class ContextManager:
    def __init__(self, max_tokens: int = 4000)
    def add_message(self, session_id, role, content, turn_id=None) -> None
    def get_history(self, session_id) -> List[MessageEntry]
    def get_recent(self, session_id, count=10) -> List[MessageEntry]
    def build_validation_prompt(self, session_id, question_type, question_text,
                                expected_context, user_transcript, max_history=6) -> str
    def build_interruption_prompt(self, session_id, transcript, current_question,
                                  tts_text, expected_context) -> str
    def clear(self, session_id) -> None
```

Token budget enforcement: estimates tokens as `total_chars / 4`. When exceeding `max_tokens`, prunes oldest non-system messages first.

#### Why was this done?
Previously, conversation history was not available to LLM calls. The ContextManager provides recent conversation context to the validation and interruption prompts, enabling the LLM to make context-aware decisions (e.g., recognizing that "no" is an answer to a yes/no question, not a correction).

---

## LESSON 53: Response Coordinator — LLM → TTS Streaming Pipeline

### File:
`backend/app/modules/conversation/application/services/response_coordinator.py`

Owns the streaming LLM → TTS pipeline. This is the most complex service in the system.

```python
@dataclass
class StreamingResult:
    classification: str
    should_advance: bool
    reason: str
    metadata: Dict[str, Any]
    token_count: int
    duration_ms: int
    time_to_first_token_ms: Optional[int]
    time_to_first_audio_ms: Optional[int]

class ResponseCoordinator:
    DELIMITER = "###METADATA###"

    def __init__(self, event_bus: EventBus, synthesize_speech, validate_response_stream)
    def set_cancellation_token(self, token: CancellationToken) -> None
    async def stream_response(self, item, transcript, session_id, turn_id, question_id,
                              turn_context=None) -> StreamingResult
```

**Streaming pipeline flow:**
1. Calls `validate_response_stream()` which yields LLM tokens as they arrive.
2. Accumulates tokens in a buffer, looking for sentence boundaries (`.!?` or 80+ chars).
3. When a sentence is complete, flushes it to TTS via `_tts_flush()` → publishes `tts_audio_chunk` events on the EventBus.
4. When the `###METADATA###` delimiter is found, flushes any remaining spoken text, then parses the JSON metadata block.
5. Waits for balanced braces before parsing JSON (handles streaming JSON).
6. Returns `StreamingResult` with classification, should_advance, reason, and timing metrics.

**Cancellation**: Checks `CancellationToken` and `turn_context.is_destroyed` on every token. Raises `CancelledError` if cancelled.

**Lenient JSON parsing**: Falls back through strict parse → single-quote replacement → unquoted key fixing → Python boolean conversion.

---

## LESSON 54: Task Router — Intent-to-Handler Mapping

### File:
`backend/app/modules/conversation/application/services/task_router.py`

Maps intent classifications to handler functions. Separated from intent detection — detection says WHAT, routing says HOW.

```python
class TaskRouter:
    def register(self, intent_type: str, handler: Callable) -> None
    def set_fallback(self, handler: Callable) -> None
    async def route(self, intent_type: str, context: Dict[str, Any]) -> Any
```

---

# PART 7: Voice Processing Bounded Context

---

## LESSON 55–60: Speech-to-Text (STT) & Text-to-Speech (TTS) Adapters

### Files:
- Interfaces: `stt_provider_interface.py`, `tts_provider_interface.py`
- Adapters: `deepgram_stt_adapter.py`, `deepgram_tts_adapter.py`
- Use Case: `synthesize_speech.py`

### STT Provider Interface

```python
class STTProviderInterface(ABC):
    async def connect(self) -> None
    async def send_audio(self, chunk: bytes) -> None
    async def receive_any(self) -> Dict[str, Any]       # Raw parsed message
    async def receive_transcript(self) -> Optional[str]  # Finalized transcripts only
    async def drain_pending(self) -> None                # Flush all pending messages
    async def close(self) -> None
```

### TTS Provider Interface

```python
class TTSProviderInterface(ABC):
    async def synthesize(self, text: str) -> bytes          # REST single-block
    async def synthesize_stream(self, text: str) -> AsyncGenerator  # Streaming chunks
    async def connect_stream(self) -> None                  # Persistent WebSocket
    async def close(self) -> None
```

### Deepgram STT Adapter

Key additions:
- **Epoch-based stale transcript detection**: Every queue item is tagged with the current epoch. When a turn advances, `advance_epoch()` increments the counter and `drain_before(epoch)` discards items from earlier epochs.
- **Queue overflow handling**: `maxsize=500`. When full, discards oldest item to make room.
- **Consecutive error backoff**: Exponential backoff (0.5s → 2.0s) on persistent WebSocket errors.
- **Auto-reconnect**: `send_audio()` detects dead connections and reconnects automatically.
- **`receive_any()`** returns data with `_epoch` key for caller-side freshness checking.

### Deepgram TTS Adapter

Now uses the **official Deepgram SDK v7.x** with WebSocket streaming:

```python
class DeepgramTTSAdapter(TTSProviderInterface):
    async def connect_stream(self) -> None
        # Opens persistent WebSocket via AsyncDeepgramClient
        # Registers event handlers (MESSAGE, OPEN, CLOSE, ERROR)
        # Starts background listener task

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]
        # Sends text + flush to WebSocket
        # Yields audio chunks as they arrive via internal queue
        # 30-second timeout per chunk prevents indefinite blocking
        # None sentinel signals end-of-stream

    async def synthesize(self, text: str) -> bytes
        # REST fallback via httpx.AsyncClient
```

**Event handling**: `_on_message` handles bytes (audio chunks → queue), `Flushed`/`Cleared` (→ None sentinel), and `Warning`/`Error`/`Metadata` (logging only).

#### Why was WebSocket streaming preferred over REST?
- **Lower TTFB**: First audio chunk arrives before the full synthesis completes.
- **Sentence-level streaming**: The ResponseCoordinator can flush sentences as they're spoken, reducing perceived latency.
- **Persistent connection**: Eliminates HTTP connection setup overhead per synthesis call.

---

# PART 8: Interruption Module

---

## LESSON 61–65: Interruption Classifier & Persistence

### Files:
- Entity: `backend/app/modules/interruption/domain/entities/interruption_entity.py`
- Interface: `backend/app/modules/interruption/domain/interfaces/interruption_repository_interface.py`
- Repository: `backend/app/modules/interruption/infrastructure/persistence/sqlite_interruption_repository.py`
- Use Cases: `classify_interruption.py`, `record_interruption.py`
- LLM Adapter: `backend/app/modules/interruption/infrastructure/external/interruption_classifier_adapter.py`
- Prompt: `backend/app/modules/interruption/infrastructure/external/prompts/interruption_prompt.py`

### ClassifyInterruption (Use Case)

```python
class ClassifyInterruption:
    _STOP_COMMANDS = {"stop", "stop talking", "be quiet", "shut up", "pause"}
    _END_COMMANDS = {"end", "end conversation", "start over", "reset", "quit", "i'm done"}

    async def execute(self, transcript, current_question="", tts_text="",
                      expected_context="", previous_answer=None, is_tts_playing=False
                      ) -> Dict[str, Any]
```

**Two-tier classification:**
1. **Deterministic routing** for system commands (sub-100ms): `stop` and `end` commands bypass the LLM entirely.
2. **LLM-based semantic classification** for everything else: Delegates to `InterruptionClassifierAdapter`.

### InterruptionClassifierAdapter (LLM)

```python
class InterruptionClassifierAdapter:
    async def classify(self, transcript, current_question, tts_text,
                       expected_context, previous_answer, is_tts_playing
                       ) -> Dict[str, Any]
```

Returns `{interrupt: bool, type: str, confidence: float}` where type is one of: `STOP`, `REPEAT`, `CORRECTION`, `ANSWER`, `END_CONVERSATION`, `NONE`.

The LLM prompt includes:
- Current question and expected context
- What the assistant is currently saying (TTS text)
- Whether TTS is currently playing
- The user's previous answer (for correction detection)
- The user's new utterance

On LLM failure/timeout (10s), returns safe default `{interrupt: False, type: "NONE", confidence: 0.0}`.

---

# PART 9: Presentation Layer & WebSocket Controller

---

## LESSON 66–69: Connection Manager, Formatter & Dependency Injection

### Files:
- Connection Manager: `backend/app/entrypoints/websocket/connection_manager.py`
- Formatter: `backend/app/entrypoints/response_formatter.py`
- DI Container: `backend/app/entrypoints/websocket/dependencies.py`

### Dependencies Container

Expanded significantly to provide all new services:

```python
# Singletons
_json_conversation_repo: JsonConversationRepository
_event_bus: EventBus
_conversation_policy: ConversationPolicy
_context_manager: ContextManager
_task_router: TaskRouter
_runtime_state_manager: RuntimeStateManager
_provider_health: ProviderHealthManager
_capability_registry: CapabilityRegistry

# Factory functions
def get_event_bus() -> EventBus
def get_conversation_policy() -> ConversationPolicy
def get_context_manager() -> ContextManager
def get_task_router() -> TaskRouter
def get_runtime_state_manager() -> RuntimeStateManager
def get_provider_health() -> ProviderHealthManager
def get_capability_registry() -> CapabilityRegistry
def get_conversation_repository() -> ConversationRepositoryInterface
def get_session_repository() -> SessionRepositoryInterface
def get_message_repository() -> MessageRepositoryInterface
def get_response_repository() -> ResponseRepositoryInterface
def get_interruption_repository() -> InterruptionRepositoryInterface
def get_stt_adapter() -> STTProviderInterface
def get_tts_adapter() -> TTSProviderInterface
def get_validation_adapter() -> ValidationProviderInterface
def get_interruption_classifier_adapter() -> InterruptionClassifierAdapter
def get_current_user(token) -> str
```

Provider health registers three providers at startup: `deepgram_stt`, `deepgram_tts`, `litellm`.

---

## LESSON 70: Master WebSocket Controller

### File:
`backend/app/entrypoints/websocket/conversation_handler.py`

This is the orchestration hub connecting all use cases, state machine transitions, audio streams, and WebSocket frames. Now 664 lines (up from ~300).

#### Dependency Injection (18 injected dependencies):
The WebSocket handler receives via FastAPI Depends:
`session_repo`, `message_repo`, `conversation_repo`, `response_repo`, `interruption_repo`, `stt_adapter`, `tts_adapter`, `validation_adapter`, `interruption_classifier`, `event_bus`, `conversation_policy`, `context_manager`, `runtime_state`, `provider_health`, `capability_registry`

#### Session Startup:
1. Authentication via `get_current_user(token)`. Rejects invalid tokens with code `4001`.
2. Session creation/recovery with user ownership verification (code `4003` for unauthorized).
3. Creates `CancellationTokenSource`, `SessionResourceManager`, and `RuntimeStateManager` session.
4. Connects STT and TTS adapters (records success/failure with `provider_health`).
5. Subscribes to EventBus events (`tts_audio_chunk`, `tts_audio_meta`, `tts_stream_end`) for audio delivery.
6. Creates `ResponseCoordinator` with cancellation token.

#### Turn Lifecycle:
1. `start_new_turn()`: Destroys previous TurnContext, creates new one, records in RuntimeStateManager.
2. `ask_current()`: Presents question, synthesizes TTS via `speak()`, advances FSM through `ASKING → WAITING_FOR_TTS → TTS_PLAYING → LISTENING`.
3. `speak(text)`: Streams TTS audio via `synthesize_stream()`, sends `tts_audio_meta` + raw bytes + `tts_stream_end`, advances STT epoch, drains stale transcripts.

#### Main Event Loop:
- Receives WebSocket frames (bytes = audio, text = JSON control messages).
- Audio frames → `stt_adapter.send_audio()` → poll `stt_adapter.receive_any()` for transcripts.
- **Epoch filtering**: Discards STT items with `_epoch < current_turn.listening_epoch`.
- Partial transcripts → `user_partial_transcript` events.
- Final transcripts → FSM guard check → interruption classification → policy routing.

#### Interruption Handling:
1. If TTS was playing when transcript arrived: Classify via LLM (`classify_interruption.execute()`).
2. If TTS was NOT playing: Default to `{interrupt: False, type: "ANSWER"}`.
3. Route through `ConversationPolicy.resolve_action()`.

#### Policy Actions:
- **STOP**: Transition to LISTENING, wait for user.
- **END_CONVERSATION**: Close session, clear context, destroy turn, create new session, replay intro.
- **REPEAT**: Call `ask_current()` to re-present the question.
- **CORRECTION**: Apply correction to TurnContext, validate corrected answer via streaming.
- **ANSWER**: Validate via streaming LLM (`_handle_streaming_answer`), advance or retry.

#### Streaming Answer Handler (`_handle_streaming_answer`):
1. Creates `response_coordinator.stream_response()` task.
2. Starts background `_drain_mic()` task that forwards mic audio to STT while LLM processes.
3. `_drain_mic` also handles `tts_interrupt` messages — cancels the LLM task.
4. After LLM completes, verifies turn ownership (`is_event_valid`), marks transcript consumed.
5. Returns structured validation result.

#### TTS Interrupt:
Client sends `tts_interrupt` JSON message → cancels `CancellationTokenSource` → creates new source → cancels active LLM task on TurnContext.

#### Cleanup (finally block):
Cancels token source, logs session/conversation/turn end, destroys TurnContext, closes STT/TTS adapters, destroys RuntimeStateManager session, releases all resources via `SessionResourceManager.release_all()`, disconnects WebSocket.

---

## LESSON 71: Main Application Entrypoint

### File:
`backend/main.py`

```python
app = FastAPI(title="Conversational Widget Platform Backend")

# API routes (registered first → take priority)
app.include_router(health_router)
app.include_router(ws_router)

# Static asset subdirectories (assets, models, ort-wasm, vad)
# Individual root-level files for VAD (silero_vad_v5.onnx, vad.worklet.bundle.min.js)
# SPA fallback — must be LAST so API routes win

@app.on_event("startup")
async def on_startup():
    init_db()
    repo = get_conversation_repository()
    available = repo.list_available()
```

Now serves the built React frontend as static files with SPA fallback routing. VAD ONNX model and WASM files are served from the root path.

---

# PART 10: Backend Test Suite

---

## LESSON 72–80: Unit & Integration Tests

### Files:
- `backend/tests/shared/test_migrations.py`: SQL table creation and migration idempotency.
- `backend/tests/shared/test_event_bus.py`: EventBus sync/async handler dispatch.
- `backend/tests/modules/session/test_session_use_cases.py`: Session CRUD operations.
- `backend/tests/modules/session/test_runtime_state_manager.py`: RuntimeStateManager state transitions.
- `backend/tests/modules/conversation/test_conversation_engine.py`: Engine question navigation.
- `backend/tests/modules/conversation/test_turn_context.py`: FSM transitions, task cancellation, correction tracking.
- `backend/tests/modules/conversation/test_validation_adapter.py`: LLM validation response parsing.
- `backend/tests/modules/conversation/test_response_coordinator.py`: Streaming LLM→TTS pipeline.
- `backend/tests/modules/conversation/test_task_router.py`: Intent-to-handler routing.
- `backend/tests/modules/conversation/test_conversation_policy.py`: Policy action resolution.
- `backend/tests/modules/conversation/test_context_manager.py`: History management and token budget.
- `backend/tests/modules/interruption/test_classify_interruption.py`: Pattern matching and LLM classification.
- `backend/tests/modules/voice/test_deepgram_stt_adapter.py`: STT epoch management and queue operations.
- `backend/tests/modules/voice/test_deepgram_tts_adapter.py`: TTS streaming and event handling.
- `backend/tests/integration/test_websocket_flow.py`: End-to-end WebSocket integration tests.

---

# PART 11: React Frontend Application

---

## LESSON 81: Global State Store (Conversation Context)

### File:
`frontend/src/context/ConversationContext.jsx`

```javascript
const initialState = {
  isOpen: false,
  sessionId: null,
  status: "idle", // idle | connecting | active | paused | completed | cancelled
  transcriptLines: [],
  partialTranscript: "",
  isSpeaking: false,
  isListening: false,
};
```

Actions: `OPEN_WIDGET`, `CLOSE_WIDGET`, `SESSION_STARTED`, `SET_LISTENING`, `RECOVER_TRANSCRIPT`, `APPEND_TRANSCRIPT_LINE`, `SET_PARTIAL_TRANSCRIPT`, `CLEAR_PARTIAL_TRANSCRIPT`, `SET_ASSISTANT_HIGHLIGHT`, `SESSION_COMPLETED`, `SESSION_CANCELLED`, `SESSION_RESET`, `RESET_FOR_NEW_SESSION`.

Note: `SESSION_STARTED` now also sets `isListening: true`. `SESSION_RESET` is new for END_CONVERSATION support.

---

## LESSON 82: Audio Pipeline Configuration

### File:
`frontend/src/audio/config/AudioConfig.js`

Centralized, observable, runtime-updateable configuration for all audio processing modules:

```javascript
const DEFAULT_AUDIO_CONFIG = {
  echoCancellation: true, noiseSuppression: true, autoGainControl: true,
  enableRNNoise: true,
  enableHighPass: true, highPassCutoff: 80,
  enableNoiseGate: true, noiseGateAttack: 0.01, noiseGateRelease: 0.1, noiseGateHold: 0.15,
  vadSensitivity: 0.5, vadFrameSize: 512,
  preRollDuration: 200, hangoverDuration: 300,
  sampleRate: 48000, frameSize: 480,
  playbackBufferSize: 5, maxQueueChunks: 200,
};

class AudioConfig {
  get(key) / getAll() / update(partial) / onChange(listener) / snapshot()
}
```

Singleton via `getAudioConfig()`. Supports runtime updates with listener notification.

---

## LESSON 83: Audio Preprocessing Pipeline

### File:
`frontend/src/audio/AudioPipeline.js`

Chains AudioWorklet processors for enterprise-grade audio preprocessing:

```
Browser Mic → RNNoise AI Denoiser → High-Pass Filter (80Hz) → Adaptive Noise Gate → Destination
```

```javascript
class AudioPipeline {
  async init(mediaStream) → MediaStreamAudioDestinationNode
  get outputStream → MediaStream   // Processed stream for VAD/MediaRecorder
  get gateOpen / noiseFloor        // Noise gate state
  stop()                           // Tear down all nodes
}
```

Each module is independently replaceable. Worklet load failures are graceful (warns and skips). The pipeline runs entirely on the client before audio is transmitted over WebSocket.

---

## LESSON 84: Audio State Machine

### File:
`frontend/src/audio/state/AudioStateMachine.js`

Independent audio pipeline lifecycle FSM (separate from the backend ConversationFSM):

```
Idle → Initializing → Listening → SpeechDetected → Streaming →
Paused → Interrupted → Recovering → Closed
```

```javascript
class AudioStateMachine {
  transition(target, reason) → bool
  onChange(listener) → unsubscribe
  snapshot() → {state, historyLength}
}
```

Maintains transition history (capped at 50) for debugging. Illegal transitions are logged as warnings and rejected.

---

## LESSON 85: Playback Queue Manager

### File:
`frontend/src/audio/playback/PlaybackQueueManager.js`

Owns queue lifecycle and buffering for audio playback:

```javascript
class PlaybackQueueManager {
  enqueue(chunk) → bool     // Overflow: drops oldest chunk
  dequeue() → chunk
  peek() → chunk
  clear() → clearedCount
  removeStale(maxAgeMs) → removedCount   // For interruption cleanup
  get size / isEmpty / droppedChunks
  snapshot() → {size, maxSize, droppedChunks, totalEnqueued, totalDequeued}
}
```

---

## LESSON 86: Flow Controller — Streaming Backpressure

### File:
`frontend/src/audio/playback/FlowController.js`

Explicit flow control for audio streaming with backpressure, overflow detection, and interruption cleanup:

```javascript
class FlowController {
  shouldPause(currentQueueSize) → bool    // 80% threshold
  shouldResume(currentQueueSize) → bool   // 50% threshold
  handleOverflow(currentQueueSize, incomingCount) → overflowCount
  cleanupAfterInterruption(queueManager) → removedCount
  reset()
}
```

Prevents unlimited memory growth under slow playback conditions.

---

## LESSON 87: Audio Health Monitor

### File:
`frontend/src/audio/health/AudioHealthMonitor.js`

Monitors runtime audio quality. Emits structured events but does NOT control conversation flow:

- **Clipping detection**: Peak amplitude > 0.98 threshold.
- **Prolonged silence**: Mic level < 0.005 for > 10 seconds.
- **Queue overflow**: Playback buffer depth > 150.

```javascript
class AudioHealthMonitor {
  start(config) / stop()
  checkFrame(samples)    // Per-frame clipping detection
  onAlert(listener) → unsubscribe
  getAlerts(since) → alerts
}
```

Singleton via `getAudioHealthMonitor()`.

---

## LESSON 88: Audio Metrics — Runtime Observability

### File:
`frontend/src/audio/metrics/AudioMetrics.js`

Observability-only metrics collection. Does NOT affect runtime behavior:

```javascript
class AudioMetrics {
  // Metrics tracked:
  micLevel, estimatedNoise, speechDetectionCount, falseVADActivations,
  totalUtteranceDurationMs, utteranceCount, interruptionCount,
  droppedFrames, playbackBufferDepth, queueLatencyMs, sttConfidence,
  preprocessingLatencyMs, ttsChunksSent, ttsChunksReceived,
  sttPartialCount, sttFinalCount, connectionResets

  get snapshot → {...metrics, sessionDurationMs, avgUtteranceDurationMs}
  reset()
}
```

Singleton via `getAudioMetrics()`.

---

## LESSON 89: Web Audio Processing & Microphone Utilities

### File:
`frontend/src/utils/audioUtils.js`

Contains functions for Web Audio API management and real-time audio volume analysis:
- **`audioVolumeTracker`**: Shared object storing normalized `mic` and `speaker` volume levels, plus `isTTSPlaying` flag.
- **`setTTSPlaying(bool)`**: Updates the TTS playing state for volume-based interruption detection.
- **`trackMicVolume(stream)`**: Connects microphone stream to `AnalyserNode` (`fftSize = 256`) and updates `audioVolumeTracker.mic` on every animation frame.
- **`createMicStream(onChunk)`**: Initializes `MediaRecorder` for `audio/webm;codecs=opus` with 100ms time slices. Returns `{stream, stop}`.
- **`playAudioBuffer(arrayBuffer, audioContext)`**: Decodes and plays raw TTS audio through speaker `AnalyserNode`.

---

## LESSON 90: VAD Hook — Voice Activity Detection

### File:
`frontend/src/hooks/useVAD.js`

Hybrid VAD hook using `@ricky0123/vad-web` (Silero V5 ONNX model):

```javascript
function useVAD({ onSpeechStart, onSpeechEnd, onInterruption, onFrameProcessed }) {
  return {
    start(stream),     // Initialize MicVAD on MediaStream
    stop(),            // Destroy VAD instance
    setTTSPlaying(bool), // Track TTS state for interruption detection
    isReady(),         // VAD initialized successfully
    isFallback(),      // VAD failed, using fallback
  }
}
```

**Interruption detection**: When `ttsPlayingRef.current` is true and VAD detects speech start, fires `onInterruption` callback instead of `onSpeechStart`. This triggers TTS stop + `tts_interrupt` message to backend.

**Graceful fallback**: If VAD initialization fails (e.g., ONNX WASM not available), sets `fallbackRef` and continues without speech detection. The legacy volume-polling mechanism in `useWebSocket` acts as safety-net fallback.

### VAD AudioWorklet

#### File: `frontend/src/vad/audio-worklet/vad-processor.js`

AudioWorklet processor for real-time PCM capture:
- Downmixes multi-channel input to mono.
- Resamples from browser sample rate to 16kHz (linear interpolation).
- Sends 30ms frames (480 samples at 16kHz) to Web Worker via `postMessage` with ArrayBuffer transfer.
- Audio passes through unchanged to output.

---

## LESSON 91: WebSocket Service

### File:
`frontend/src/services/websocketService.js`

Extracted WebSocket connection factory:

```javascript
function createConversationSocket({ conversationType, sessionId, onEvent, onAudio }) {
  // Creates WebSocket to /ws/{conversation_type}?session_id={id}
  // binaryType = "arraybuffer"
  // Routes string messages to onEvent(JSON.parse), binary to onAudio(buffer)
  return { socket, sendAudioChunk(buffer), sendJson(obj), close() }
}
```

---

## LESSON 92: Deepgram Audio Hook

### File:
`frontend/src/hooks/useDeepgramAudio.js`

Manages microphone streaming and TTS playback hooks:
- **`startMic(onChunk)`**: Begins streaming mic chunks via `createMicStream`. Returns `{stream}` for VAD integration.
- **`playTTS(arrayBuffer)`**: Single-buffer TTS playback (fallback).
- **`startStreamingTTS()`**: Creates streaming player that accepts incremental `appendChunk()` calls.
- **`stopTTS()`**: Stops active audio playback immediately for voice barge-in.

---

## LESSON 93: WebSocket Integration Hook

### File:
`frontend/src/hooks/useWebSocket.js`

Connects the React UI to the backend WebSocket endpoint. Now 238 lines with VAD integration.

**VAD Integration:**
- Starts Silero V5 ONNX VAD on the same MediaStream as the MediaRecorder.
- VAD `onInterruption` callback: stops TTS, sends `tts_interrupt` to backend.
- Legacy volume-polling fallback: 100ms interval checks for sustained mic volume > 15 for 300ms during TTS playback.

**Event handling:**
- `session_started`: Saves session_id, dispatches to context.
- `transcript_recovery`: Reconstructs past messages.
- `user_partial_transcript` / `user_transcript`: Updates transcript display.
- `tts_audio_meta`: Sets `is_streaming=true`, creates streaming player, sets TTS playing state.
- `tts_stream_end`: Calls `player.endStream()`, waits for `onEnded`, sends `tts_end` to backend.
- `session_reset`: Clears transcript, dispatches reset.

**Audio routing:**
- If streaming player exists: `player.appendChunk(uint8array)`.
- If TTS playing but no player: fallback `playTTS(arrayBuffer)`.
- If neither: race condition handler — creates player, buffers chunk.

---

# PART 12: React Frontend UI Components

---

## LESSON 94: Holographic Orb Component

### File:
`frontend/src/components/HolographicOrb.jsx`

An interactive 3D visualizer orb reflecting AI state:
- **Dynamic State Gradients**: Changes orb glow and radial background gradients based on current state (`connecting`, `listening`, `speaking`, `thinking`, `completed`).
- **Concentric Ring Animations**: Three animated visualizer rings (outer, mid, inner) that rotate and dynamically expand based on real-time volume levels from `audioVolumeTracker`.
- **Mouse Parallax Tilt**: Calculates cursor position relative to the orb container and applies 3D perspective tilt (`rotateX` / `rotateY`).

---

## LESSON 95: Subtitle Overlay Component

### File:
`frontend/src/components/TranscriptOverlay.jsx`

Renders real-time conversational subtitles:
- Displays current speaker labels (*"AETHER AI"* vs *"YOU"*).
- Shows live partial speech transcription text in real-time.
- Automatically scrolls to the newest line.

---

## LESSON 96: Control Bar Component

### File:
`frontend/src/components/ControlBar.jsx`

A glassmorphic HUD toolbar featuring:
- **Status Indicator**: Displays active status text.
- **Mic Mute Toggle**: Mutes/unmutes local microphone streaming.
- **Pack Settings Modal Toggle**: Opens the conversation pack drawer.
- **Session Power Button**: Ends session and resets connection.

---

## LESSON 97: Settings Panel Component

### File:
`frontend/src/components/SettingsPanel.jsx`

A modal drawer allowing users to switch between conversation packs. Selecting a new pack resets the session storage and re-handshakes with the backend.

---

## LESSON 98: Home Page & Application Container

### Files:
- `frontend/src/pages/HomePage.jsx`
- `frontend/src/App.jsx`
- `frontend/src/main.jsx`
- `frontend/src/index.css`

Assembles the complete visual experience:
1. Ambient volumetric background glows (`blur-[100px]`).
2. Floating particle layer simulating cinematic dust drift.
3. HUD top header with status badges.
4. Central `HolographicOrb` and `TranscriptOverlay`.
5. Bottom `ControlBar` and `SettingsPanel` overlay.

---

# ARCHITECTURE COMPLIANCE ASSESSMENT

## ✅ Clean Architecture Rules Followed

1. **Domain layer has zero infrastructure imports**: Entities, interfaces, FSM, TurnContext, and ConversationPolicy import only from `app.shared` (logging, config) and each other. No SQLite, no Deepgram, no LiteLLM.

2. **Application layer depends only on domain interfaces**: Use cases (`CreateSession`, `ValidateResponse`, etc.) accept repository/provider interfaces via constructor injection.

3. **Infrastructure implements domain interfaces**: `SqliteSessionRepository` implements `SessionRepositoryInterface`, `LiteLLMValidationAdapter` implements `ValidationProviderInterface`, `DeepgramSTTAdapter` implements `STTProviderInterface`.

4. **Presentation uses DI for all dependencies**: The WebSocket handler receives all repositories, adapters, and services via FastAPI `Depends()`. No direct instantiation of infrastructure classes in the handler.

5. **Exception boundaries maintained**: Domain exceptions (`DomainError` hierarchy) used in domain/application layers. Framework exceptions (`WebSocketDisconnect`) caught only in the presentation layer.

## ⚠️ Minor Deviations

1. **`ClassifyInterruption` type-hints concrete adapter**: The constructor accepts `Optional[InterruptionClassifierAdapter]` (concrete class) instead of an abstract interface. This is acceptable because the interruption classifier is only used within the interruption module's application layer, and the adapter is injected (not instantiated).

2. **`conversation_handler` imports domain models directly**: The WebSocket handler imports `ConversationState`, `TurnContext`, `ConversationPolicy`, and `PolicyAction`. In strict Clean Architecture, the presentation layer should only interact through application services. However, in a monolith where the handler is the orchestration hub, direct FSM manipulation is pragmatic and the trade-off is justified by the complexity of the turn lifecycle.

3. **`interruption_classifier_adapter` uses `AsyncOpenAI` directly**: This is within the infrastructure layer and is the expected location for external service clients.

## Assessment Summary

The codebase follows **Monolithic Clean Architecture** consistently. All five bounded contexts (session, message, conversation, voice, interruption) maintain proper layer separation. The shared cross-cutting concerns (EventBus, CancellationToken, PipelineLogger, ErrorClassifier, RuntimeLimits, ProviderHealthManager, CapabilityRegistry, SessionResourceManager) live in `app/shared/` and are imported by all layers as needed. The DI container in `dependencies.py` is the single composition root.

---

# CONGRATULATIONS!

You have completed the entire Codebase Study Guide! You now understand every configuration setting, database table, domain entity, FSM state transition, STT/TTS adapter, LLM validation pipeline, streaming response coordinator, cancellation framework, event bus, provider health circuit breaker, resource manager, WebSocket frame handler, VAD integration, audio preprocessing pipeline, and React visualizer component in the project.
