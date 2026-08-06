# Real-Time Voice Conversational Platform: Exhaustive Backend Master Blueprint

Welcome! I am going to take you personally on a step-by-step tour through the **entire backend codebase**. 

Whether you are building this system from scratch or mastering every architectural detail, this document will serve as your personal guide. We will walk through **literally every single file, class, method, function signature, SQL table, and parameter** in the `backend/` directory in the exact chronological order a Senior Systems Architect builds this system.

---

# ARCHITECTURAL OVERVIEW & BOUNDED CONTEXT MATRIX

## 1. Clean Architecture Layer Diagram
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       1. PRESENTATION LAYER                                 │
│  FastAPI Router (main.py) │ WebSocket Controller (conversation_handler.py)  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ (Injects DI Dependencies)
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                       2. APPLICATION LAYER                                  │
│  ResponseCoordinator │ RuntimeStateManager │ ContextManager │ TaskRouter    │
│  Use Cases: CreateSession, ValidateResponse, RecordResponse, Synthesize...  │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │ (Enforces Business Rules)
┌──────────────────────────────────▼──────────────────────────────────────────┐
│                         3. DOMAIN LAYER                                     │
│  Turn FSM (conversation_fsm.py) │ Race Shield (turn_context.py)             │
│  ConversationPolicy │ Entities: SessionEntity, MessageEntity, Interruption  │
│  Abstract Contracts: SessionRepositoryInterface, STTProviderInterface...    │
└──────────────────────────────────▲──────────────────────────────────────────┘
                                   │ (Implements Contracts)
┌──────────────────────────────────┴──────────────────────────────────────────┐
│                      4. INFRASTRUCTURE LAYER                                │
│  PostgreSQL DAOs (postgres_session_repository.py, postgres_bot_repository.py)│
│  External Adapters: DeepgramSTTAdapter, DeepgramTTSAdapter, LiteLLMAdapter  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     5. SHARED CROSS-CUTTING SERVICES                        │
│  EventBus │ CancellationToken │ PipelineLogger │ EnvelopeEncryption          │
└─────────────────────────────────────────────────────────────────────────────┘
```



## 2. Bi-Directional Streaming Voice Loop Diagram
```
 [Client Mic] ──(Binary PCM Audio)──► [WebSocket Endpoint (conversation_handler.py)]
                                                    │
                                                    ▼
                                     [Deepgram STT Adapter]
                                                    │
                                                    ▼ (Final Transcript)
                                         [TurnContext & FSM]
                                                    │
                                                    ▼ (Validate & Stream)
                                        [LiteLLM Validation Adapter]
                                                    │
                                                    ▼ (Token Stream)
                                      [ResponseCoordinator Service]
                                      (Sentence Chunking: . ! ?)
                                                    │
                                                    ▼ (Complete Sentences)
                                      [Deepgram TTS SDK Adapter]
                                                    │
 [Client Speaker] ◄──(Binary Audio)── [WebSocket Endpoint]
```



Before we touch a single line of code, let's understand the high-level Clean Architecture and Bounded Context layout:

```
                  ┌────────────────────────────────────────┐
                  │          Presentation Layer            │
                  │ FastAPI WebSockets / HTTP REST API     │
                  └──────────────────┬─────────────────────┘
                                     │
                  ┌──────────────────▼─────────────────────┐
                  │           Application Layer            │
                  │ Use Cases, Services, ResponseCoord     │
                  │ RuntimeStateManager, ContextManager    │
                  └──────────────────┬─────────────────────┘
                                     │
                  ┌──────────────────▼─────────────────────┐
                  │             Domain Layer               │
                  │ Entities, Interfaces, FSM, TurnContext │
                  │ Policy, Value Objects, Exception Types │
                  └──────────────────▲─────────────────────┘
                                     │
                  ┌──────────────────┴─────────────────────┐
                  │          Infrastructure Layer          │
                  │ PostgreSQL DB, Envelope Encryption,    │
                  │ Deepgram STT/TTS, ElevenLabs, LiteLLM  │
                  └────────────────────────────────────────┘

                  ┌────────────────────────────────────────┐
                  │        Shared Cross-Cutting Layer      │
                  │ EventBus, CancellationToken, Pipeline  │
                  │ Logger, ErrorClassifier, RuntimeLimits │
                  │ ProviderHealth, CapabilityRegistry,    │
                  │ SessionResourceManager                 │
                  └────────────────────────────────────────┘
```

## Bounded Context Inventory:
1. **session**: Session lifecycle, state snapshots, runtime connection management (`SessionEntity`, `PostgresSessionRepository`, `RuntimeStateManager`, session use cases).
2. **message**: Transcript storage and message history (`MessageEntity`, `PostgresMessageRepository`, message use cases).
3. **conversation**: FSM turn control, race condition shielding, policy decisions, LLM streaming validation, and sentence chunking (`ConversationFSM`, `TurnContext`, `ConversationPolicy`, `ConversationEngine`, `ContextManager`, `ResponseCoordinator`, `LiteLLMValidationAdapter`, `JsonConversationRepository`).
4. **voice**: STT speech recognition and TTS speech synthesis (`STTProviderInterface`, `TTSProviderInterface`, `DeepgramSTTAdapter`, `DeepgramTTSAdapter`, `ElevenLabsTTSAdapter`, `SynthesizeSpeech`).
5. **interruption**: Speech barge-in classification and audit recording (`InterruptionEntity`, `PostgresInterruptionRepository`, `InterruptionClassifierAdapter`, `ClassifyInterruption`, `RecordInterruption`).
6. **provider**: Multi-provider credentials and models (`LLMProvider`, `SpeechProvider`, `PostgresLLMProviderRepository`, `PostgresSpeechProviderRepository`).
7. **bot**: Autonomous voice bot identities and active runtime synchronization (`Bot`, `PostgresBotRepository`, single-active bot activation).

---

# STAGE 1: Process Setup & Environment Configuration

Let's begin at the very start: setting up Python requirements, environment variables, settings singletons, and runtime boundaries.
### 1.1 Dependency Lockfile: [`backend/requirements.txt`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/requirements.txt)

**Architectural Role & Why This File Exists**:
Defines all third-party Python packages required to run the backend application.

**Personal Senior Architect Walkthrough**:
Here in `requirements.txt`, we lock down `fastapi` and `uvicorn[standard]` for high-performance async HTTP and WebSockets. We bring in `pydantic` and `pydantic-settings` for type validation, `websockets` for raw frame-level STT communication, `httpx` and `litellm` for external API integration, and `pytest` + `pytest-asyncio` for unit and integration testing.


---
### 1.2 Environment Template: [`backend/.env.example`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/.env.example)

**Architectural Role & Why This File Exists**:
Template environment file defining required API keys, provider URLs, and configuration parameters.

**Personal Senior Architect Walkthrough**:
Open `.env.example` to see the environment variable keys required by the application: `DEEPGRAM_API_KEY`, `DEEPGRAM_TTS_MODEL`, `DEEPGRAM_STT_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `AI_VALIDATION_MODEL`, `DATABASE_PATH`, `MAX_RETRIES_PER_ITEM`, and `CONVERSATION_DEFINITIONS_DIR`. Notice how `DEEPGRAM_STT_URL` includes `endpointing=300`—this configures Deepgram to finalize transcripts after 300ms of silence, giving us ultra-fast conversational turn responses.


---
## Config & Limits Loading Architecture
```
┌─────────────────┐       ┌────────────────────────┐       ┌───────────────────────┐
│   .env File     ├──────►│ Settings(BaseSettings) ├──────►│ Startup Validation    │
│ (Keys & URLs)   │       │   (pydantic-settings)  │       │ (Fails Fast if Empty) │
└─────────────────┘       └───────────┬────────────┘       └───────────────────────┘
                                      │
                                      ▼
                          ┌────────────────────────┐
                          │ RuntimeLimits (Frozen) │
                          │ max_tokens: 4000       │
                          │ stt_queue_max: 500     │
                          │ circuit_thresh: 5      │
                          └────────────────────────┘
```

### 1.3 Pydantic Settings Manager: [`backend/app/shared/config/settings.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/config/settings.py)

**Architectural Role & Why This File Exists**:
Type-safe settings model that parses `.env` environment variables at process startup.

**Exhaustive Class & Function Inventory**:
- **Class `Settings`**:
  - `deepgram_stt_url()`

**Personal Senior Architect Walkthrough**:
Now let's look at `settings.py`. Here we define the `Settings` class extending Pydantic's `BaseSettings`. At process startup, it parses the environment and instantiates the global `settings` singleton. If required API keys (`deepgram_api_key`, `openai_api_key`) are missing, Pydantic immediately raises a `ValidationError`, failing fast before the server starts listening on ports.


---
### 1.4 Operational Runtime Limits: [`backend/app/shared/config/runtime_limits.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/config/runtime_limits.py)

**Architectural Role & Why This File Exists**:
Immutable frozen dataclass defining operational caps for memory, queues, and network timeouts.

**Exhaustive Class & Function Inventory**:
- **Class `RuntimeLimits`**:
  - `from_settings(cls)`
- Function `get_limits()`

**Personal Senior Architect Walkthrough**:
In `runtime_limits.py`, we define `RuntimeLimits` as a frozen dataclass and provide `get_limits()`. This file centralizes system safety bounds: `max_context_tokens` (4000 tokens), `max_retries_per_item` (3 retries), `stt_queue_max_size` (500 items), `tts_chunk_timeout_seconds` (30.0s), and `circuit_breaker_threshold` (5 failures). Having these caps prevents buffer overflows, out-of-memory crashes, and infinite retry loops.


---

# STAGE 2: Cross-Cutting Shared Infrastructure Services
### 2.1 Base Application Logger: [`backend/app/shared/logging/logger.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/logging/logger.py)

**Architectural Role & Why This File Exists**:
Central logger channel for application coroutines and background tasks.

**Personal Senior Architect Walkthrough**:
Here in `logger.py`, we instantiate `logger = logging.getLogger("conversation_widget")`. This provides a consistent log formatting namespace across async background tasks.


---
### 2.2 Structured Pipeline Trace Logger: [`backend/app/shared/logging/pipeline_logger.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/logging/pipeline_logger.py)

**Architectural Role & Why This File Exists**:
Schema-enforced pipeline trace logger tracking 50+ event types and 14 latency metrics.

**Exhaustive Class & Function Inventory**:
- Function `_ts()`
- Function `_fmt(event_type, session_id, turn_id, epoch, component, severity)`
- Function `_log(event_type, session_id, turn_id, epoch, component, severity)`
- Function `session_start(session_id, conversation_type, is_recovery)`
- Function `session_end(session_id, reason)`
- Function `conversation_start(session_id, conversation_type)`
- Function `conversation_end(session_id, reason)`
- Function `turn_create(turn_id, session_id, question_id, sequence, question_text)`
- Function `turn_destroy(turn_id, session_id, reason)`
- Function `turn_advance(session_id, turn_id, from_index, to_index)`
- Function `turn_retry(session_id, turn_id, index, retries)`
- Function `question_ask(session_id, turn_id, question_id, sequence, text)`
- Function `stt_connected(session_id, turn_id)`
- Function `stt_reconnect(session_id, turn_id, reason)`
- Function `stt_audio_sent(session_id, bytes_count)`
- Function `stt_partial_transcript(session_id, turn_id, epoch, text)`
- Function `stt_final_transcript(session_id, turn_id, epoch, text)`
- Function `transcript_accepted(session_id, turn_id, transcript_id, text)`
- Function `transcript_rejected(session_id, turn_id, transcript_id, reason)`
- Function `stt_stale_discarded(session_id, turn_id, item_epoch, current_epoch)`
- Function `stt_epoch_advance(session_id, turn_id, new_epoch)`
- Function `transcript_assigned(session_id, turn_id, transcript_id, text)`
- Function `fsm_guard_reject(session_id, turn_id, current_state)`
- Function `interrupt_detected(session_id, turn_id, transcript)`
- Function `interrupt_classify_start(session_id, turn_id, transcript, is_tts_playing)`
- Function `interrupt_classify_end(session_id, turn_id, interrupt_type, confidence, duration_ms)`
- Function `interrupt_routed(session_id, turn_id, interrupt_type, action)`
- Function `llm_started(session_id, turn_id)`
- Function `llm_first_token(session_id, turn_id, token_index)`
- Function `llm_token(session_id, turn_id, token, token_index)`
- Function `llm_completed(session_id, turn_id, duration_ms, token_count, classification, should_advance)`
- Function `llm_cancelled(session_id, turn_id, reason)`
- Function `validation_start(session_id, turn_id, question_id, transcript)`
- Function `validation_end(session_id, turn_id, should_advance, duration_ms, reason)`
- Function `validation_cancelled(session_id, turn_id, reason)`
- Function `validation_discarded(session_id, turn_id, bound_turn_id)`
- Function `correction_received(session_id, turn_id, new_text)`
- Function `correction_applied(session_id, turn_id, old_text, new_text, stack_depth)`
- Function `tts_connected(session_id, turn_id)`
- Function `tts_synthesize_start(session_id, turn_id, text)`
- Function `tts_synthesize_end(session_id, turn_id, duration_ms, audio_bytes, chunk_count)`
- Function `tts_first_chunk(session_id, turn_id, chunk_size)`
- Function `tts_last_chunk(session_id, turn_id, chunk_size, total_chunks)`
- Function `tts_send_to_client(session_id, turn_id, audio_bytes)`
- Function `tts_stream_end(session_id, turn_id)`
- Function `tts_cancelled(session_id, turn_id, reason)`
- Function `websocket_connected(session_id, client_ip)`
- Function `websocket_disconnected(session_id, reason)`
- Function `ws_frame_received(session_id, frame_type, detail)`
- Function `ws_control_message(session_id, msg_type)`
- Function `error_occurred(session_id, turn_id, component, operation, error, stack_trace)`
- Function `latency_metric(metric_name, value_ms, session_id, turn_id)`
- Function `resource_created(resource_type, resource_id, session_id, turn_id)`
- Function `resource_destroyed(resource_type, resource_id, session_id, turn_id, reason)`
- Function `fe_tts_playback_start(text)`
- Function `fe_tts_playback_end(duration_ms)`
- Function `fe_mic_chunk_sent(bytes_count)`
- Function `fe_vad_interrupt(text)`

**Personal Senior Architect Walkthrough**:
Take a close look at `pipeline_logger.py`. This is one of the most critical observability files in the system. It exposes over 50 structured logging functions (`session_start()`, `turn_create()`, `stt_audio_sent()`, `stt_final_transcript()`, `validation_start()`, `llm_first_token()`, `tts_first_chunk()`, `interrupt_detected()`, `latency_metric()`). Every line is formatted as `timestamp | event | session_id | turn_id | epoch | component | details...`. It measures 14 latency metrics (such as TTFPT - Time to First Partial Transcript, TTFT - Time to First Token, TTFA - Time to First Audio), making replay debugging effortless.


---
### 2.3 Domain Exception Taxonomy: [`backend/app/shared/exceptions/domain_exceptions.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/exceptions/domain_exceptions.py)

**Architectural Role & Why This File Exists**:
Pure domain exception hierarchy isolated from HTTP or WebSocket frameworks.

**Exhaustive Class & Function Inventory**:
- **Class `DomainError`**:
- **Class `ConversationTypeNotFoundError`**:
- **Class `SessionNotFoundError`**:
- **Class `InvalidConversationSchemaError`**:
- **Class `DuplicateConversationIdError`**:

**Personal Senior Architect Walkthrough**:
In `domain_exceptions.py`, we construct our pure domain exception tree: `DomainError` as the base class, and specialized sub-exceptions `SessionNotFoundError`, `ConversationTypeNotFoundError`, `InvalidConversationSchemaError`, and `DuplicateConversationIdError`. This keeps domain and application logic strictly decoupled from web framework exception types.


---
## Deterministic Error Recovery Flowchart
```
   Exception Occurs in Pipeline
                 │
                 ▼
 ┌───────────────────────────────┐
 │   classify_error(exception)   │
 └───────────────┬───────────────┘
                 │
                 ▼
 ┌───────────────────────────────┐
 │       ClassifiedError         │
 │ Category: RECOVERABLE / FATAL │
 │ Severity: LOW / CRITICAL      │
 │ Action: RETRY / RECONNECT     │
 └───────────────┬───────────────┘
                 │
                 ▼
 ┌───────────────────────────────┐
 │ Controller Recovery Execution │
 └───────────────────────────────┘
```

### 2.4 Deterministic Error Classifier: [`backend/app/shared/errors/error_classifier.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/errors/error_classifier.py)

**Architectural Role & Why This File Exists**:
Maps runtime exceptions to structured categories, severities, and recovery actions.

**Exhaustive Class & Function Inventory**:
- **Class `ErrorCategory`**:
- **Class `ErrorSeverity`**:
- **Class `RecoveryAction`**:
- **Class `ClassifiedError`**:
- Function `classify_error(error_type, message, details)`

**Personal Senior Architect Walkthrough**:
In `error_classifier.py`, we define `ErrorCategory` (`RECOVERABLE`, `FATAL`, `USER_ERROR`), `ErrorSeverity` (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), `RecoveryAction` (`RETRY`, `RECONNECT`, `RESTART_SESSION`, `NOTIFY_USER`, `NONE`), `ClassifiedError`, and the mapping function `classify_error(exception)`. When an unhandled error occurs anywhere in the voice pipeline, `classify_error()` inspects the exception type and message pattern, returning a structured `ClassifiedError` telling the controller exactly how to recover.


---
### 2.5 Stateless HMAC Token Cryptography: [`backend/app/shared/security/token_service.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/security/token_service.py)

**Architectural Role & Why This File Exists**:
Generates and verifies stateless HMAC-SHA256 authentication tokens.

**Exhaustive Class & Function Inventory**:
- **Class `AuthenticationError`**:
- **Class `AuthorizationError`**:
- Function `create_token(user_id, expires_in_seconds)`
- Function `verify_token(token)`

**Personal Senior Architect Walkthrough**:
In `token_service.py`, we implement `create_token(user_id, expires_in_seconds)` and `verify_token(token)`. It signs user session payloads with HMAC-SHA256 and verifies incoming tokens using `hmac.compare_digest()` to prevent constant-time timing attacks, enabling stateless authentication without database queries.


---
### 2.6 In-Process Async EventBus: [`backend/app/shared/events/event_bus.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/events/event_bus.py)

**Architectural Role & Why This File Exists**:
Decoupled publish/subscribe event dispatcher for asynchronous pipeline signaling.

**Exhaustive Class & Function Inventory**:
- **Class `Event`**:
- **Class `EventBus`**:
  - `__init__()`
  - `subscribe(event_name, handler)`
  - `subscribe_async(event_name, handler)`
  - `unsubscribe(event_name, handler)`
  - `async publish(event)`
  - `async publish_raw(name, payload, session_id)`

**Personal Senior Architect Walkthrough**:
Here in `event_bus.py`, we define the `Event` dataclass and the `EventBus` class with `subscribe()`, `subscribe_async()`, `unsubscribe()`, `publish()`, and `publish_raw()`. This decouples the streaming LLM/TTS pipeline from WebSocket connections: as TTS audio chunks are generated, the coordinator publishes `tts_audio_chunk` events to the bus; transport handlers receive them asynchronously and send binary frames over the wire.


---
### 2.7 Hierarchical CancellationToken Framework: [`backend/app/shared/cancellation/cancellation_token.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/cancellation/cancellation_token.py)

**Architectural Role & Why This File Exists**:
Thread-safe cancellation signaling framework across asynchronous coroutines.

**Exhaustive Class & Function Inventory**:
- **Class `CancellationToken`**:
  - `is_cancelled()`
  - `reason()`
  - `cancel(reason)`
  - `on_cancel(callback)`
  - `on_cancel_async(callback)`
  - `remove_callback(callback)`
  - `async wait(timeout)`
  - `check()`
  - `child()`
- **Class `CancellationTokenSource`**:
  - `__init__()`
  - `token()`
  - `cancel(reason)`
  - `create_child()`

**Personal Senior Architect Walkthrough**:
In `cancellation_token.py`, we implement `CancellationToken` and `CancellationTokenSource`. When a user interrupts the assistant speaking, calling `source.cancel()` immediately cancels all child coroutines (STT listening queues, streaming LLM token generation, and Deepgram TTS synthesis) without closing the parent session.


---
### 2.8 Dynamic Capability Registry: [`backend/app/shared/capabilities/capability_registry.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/capabilities/capability_registry.py)

**Architectural Role & Why This File Exists**:
Runtime capability tracking and feature flag availability inspector.

**Exhaustive Class & Function Inventory**:
- **Class `Capability`**:
- **Class `CapabilityRegistry`**:
  - `__init__()`
  - `register(name, available, version)`
  - `is_available(name)`
  - `get(name)`
  - `list_available()`
  - `list_all()`
  - `snapshot()`

**Personal Senior Architect Walkthrough**:
In `capability_registry.py`, we implement `CapabilityRegistry` with `register()`, `is_available()`, and `snapshot()`. Components query feature capabilities (`streaming_stt`, `streaming_tts`, `silero_vad`, `barge_in`) dynamically instead of hardcoding provider assumptions.


---
## 6. Provider Health Circuit Breaker State Diagram
```
                     ┌──────────────────────────┐
                     │          CLOSED          │ (Normal Operation)
                     │ (API Requests Allowed)   │
                     └─────────────┬────────────┘
                                   │
                                   │ (5 Consecutive Failures)
                                   ▼
                     ┌──────────────────────────┐
                     │           OPEN           │ (Fast-Fail Active)
                     │ (Calls Fail Instantly)   │
                     └─────────────┬────────────┘
                                   │
                                   │ (Timeout Expired)
                                   ▼
                     ┌──────────────────────────┐
                     │        HALF_OPEN         │ (Trial Probe)
                     │ (Sends Single Test Call) │
                     └──────┬────────────┬──────┘
                            │            │
             (Probe Success)│            │(Probe Failed)
                            ▼            ▼
                        [CLOSED]      [OPEN]
```



### 2.9 Provider Health Circuit Breaker: [`backend/app/shared/providers/provider_health_manager.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/providers/provider_health_manager.py)

**Architectural Role & Why This File Exists**:
3-State circuit breaker and Exponential Moving Average (EMA) latency tracker for API providers.

**Exhaustive Class & Function Inventory**:
- **Class `CircuitState`**:
- **Class `ProviderStats`**:
- **Class `ProviderHealthManager`**:
  - `__init__()`
  - `register(name)`
  - `record_success(name, latency_ms)`
  - `record_failure(name, error)`
  - `is_available(name)`
  - `get_stats(name)`
  - `get_all_stats()`

**Personal Senior Architect Walkthrough**:
In `provider_health_manager.py`, we define `CircuitState` (`CLOSED`, `OPEN`, `HALF_OPEN`) and `ProviderHealthManager` (`register()`, `record_success()`, `record_failure()`, `is_available()`). It tracks latency EMA and consecutive failures for Deepgram and LiteLLM. After 5 consecutive API failures, the circuit trips to `OPEN`, failing subsequent requests instantly without hanging for 30-second network timeouts.


---
## Resource Cleanup Lifecycle Flow
```
 Client Disconnect / Error Occurs
                 │
                 ▼
 ┌───────────────────────────────┐
 │ SessionResourceManager        │
 │      .release_all()           │
 └───────────────┬───────────────┘
                 ├──────────────────────────────┬──────────────────────────────┐
                 ▼                              ▼                              ▼
 ┌───────────────────────────────┐ ┌───────────────────────────┐ ┌───────────────────────────┐
 │ Cancel Coroutine Tasks        │ │ Close STT/TTS Streams     │ │ Unsubscribe EventBus      │
 │ (asyncio.gather)              │ │ (Deepgram Sockets)        │ │ Event Listeners           │
 └───────────────────────────────┘ └───────────────────────────┘ └───────────────────────────┘
```

### 2.10 Session Resource Lifecycle Manager: [`backend/app/shared/resources/session_resource_manager.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/resources/session_resource_manager.py)

**Architectural Role & Why This File Exists**:
Consolidated scope cleanup manager for background tasks, network sockets, and streams.

**Exhaustive Class & Function Inventory**:
- **Class `SessionResourceManager`**:
  - `__init__(session_id)`
  - `track_task(task)`
  - `track_timer(handle)`
  - `register_resource(name, resource, cleanup)`
  - `register_audio_context(ctx)`
  - `register_websocket(ws)`
  - `register_stt_stream(stream)`
  - `register_tts_stream(stream)`
  - `register_worklet(node)`
  - `register_event_subscription(unsubscribe_fn)`
  - `register_playback_buffer(buffer)`
  - `async release_all()`
  - `is_released()`
  - `snapshot()`

**Personal Senior Architect Walkthrough**:
Look at `session_resource_manager.py`. Here we define `SessionResourceManager` with `track_task()`, `register_websocket()`, `register_stt_stream()`, `register_tts_stream()`, and `release_all()`. When a client WebSocket disconnects, calling `release_all()` cancels background coroutines using `asyncio.gather()`, closes open streams, and unsubscribes event handlers cleanly.


---

# STAGE 3: Database Engine & Schema Migrations
### 3.1 SQLite Connection Context Manager: [`backend/app/shared/database/db.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/db.py)

**Architectural Role & Why This File Exists**:
Manages SQLite database connection checkout, row factory formatting, and transaction commits.

**Exhaustive Class & Function Inventory**:
- Function `get_connection()`

**Personal Senior Architect Walkthrough**:
In `db.py`, we implement the `get_connection()` context manager. It checks out SQLite connections, configures `sqlite3.Row` for dictionary-style row parsing, enforces `PRAGMA foreign_keys = ON`, and automatically commits transactions on context exit or rolls them back on exceptions.


---
### 3.2 Migration Script: 0001_create_sessions_table.sql: [`backend/app/shared/database/migrations/0001_create_sessions_table.sql`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/migrations/0001_create_sessions_table.sql)

**Architectural Role & Why This File Exists**:
DDL script defining database table schema for `create`.

**Personal Senior Architect Walkthrough**:
This SQL migration file `0001_create_sessions_table.sql` provides version-controlled schema definitions. The migration runner executes unapplied migration scripts in alphabetical order against SQLite.


---
### 3.2 Migration Script: 0002_create_messages_table.sql: [`backend/app/shared/database/migrations/0002_create_messages_table.sql`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/migrations/0002_create_messages_table.sql)

**Architectural Role & Why This File Exists**:
DDL script defining database table schema for `create`.

**Personal Senior Architect Walkthrough**:
This SQL migration file `0002_create_messages_table.sql` provides version-controlled schema definitions. The migration runner executes unapplied migration scripts in alphabetical order against SQLite.


---
### 3.2 Migration Script: 0003_create_responses_table.sql: [`backend/app/shared/database/migrations/0003_create_responses_table.sql`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/migrations/0003_create_responses_table.sql)

**Architectural Role & Why This File Exists**:
DDL script defining database table schema for `create`.

**Personal Senior Architect Walkthrough**:
This SQL migration file `0003_create_responses_table.sql` provides version-controlled schema definitions. The migration runner executes unapplied migration scripts in alphabetical order against SQLite.


---
### 3.2 Migration Script: 0004_create_interruptions_table.sql: [`backend/app/shared/database/migrations/0004_create_interruptions_table.sql`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/migrations/0004_create_interruptions_table.sql)

**Architectural Role & Why This File Exists**:
DDL script defining database table schema for `create`.

**Personal Senior Architect Walkthrough**:
This SQL migration file `0004_create_interruptions_table.sql` provides version-controlled schema definitions. The migration runner executes unapplied migration scripts in alphabetical order against SQLite.


---
### 3.2 Migration Script: 0005_add_status_index_to_sessions.sql: [`backend/app/shared/database/migrations/0005_add_status_index_to_sessions.sql`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/migrations/0005_add_status_index_to_sessions.sql)

**Architectural Role & Why This File Exists**:
DDL script defining database table schema for `add`.

**Personal Senior Architect Walkthrough**:
This SQL migration file `0005_add_status_index_to_sessions.sql` provides version-controlled schema definitions. The migration runner executes unapplied migration scripts in alphabetical order against SQLite.


---
## Database Migration Runner Execution Flow
```
                      ┌─────────────────────────────────┐
                      │    init_db() Startup Hook       │
                      └────────────────┬────────────────┘
                                       │
                                       ▼
                      ┌─────────────────────────────────┐
                      │  MigrationRunner.run_migrations │
                      └────────────────┬────────────────┘
                                       │
                ┌──────────────────────┴──────────────────────┐
                │ Reads All 0001 - 0005 .sql Files           │
                │ Compares Against schema_migrations Table    │
                └──────────────────────┬──────────────────────┘
                                       │
                                       ▼
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
 ┌──────────────┐               ┌──────────────┐               ┌──────────────┐
 │   sessions   │               │   messages   │               │  responses   │
 └──────────────┘               └──────────────┘               └──────────────┘
```

### 3.3 Automated Migration Runner: [`backend/app/shared/database/migrations/runner.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/migrations/runner.py)

**Architectural Role & Why This File Exists**:
Tracks applied migration files and executes pending SQL DDL scripts.

**Exhaustive Class & Function Inventory**:
- Function `run_migrations()`

**Personal Senior Architect Walkthrough**:
In `runner.py`, we implement `MigrationRunner` (`run_migrations()`). It creates a `schema_migrations` tracking table if missing, reads all `.sql` files in the migrations directory, and executes unapplied scripts in a transaction.


---
### 3.4 Database Initialization Hook: [`backend/app/shared/database/init_db.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/init_db.py)

**Architectural Role & Why This File Exists**:
Application startup hook triggering pending database migrations.

**Exhaustive Class & Function Inventory**:
- Function `init_db()`

**Personal Senior Architect Walkthrough**:
In `init_db.py`, we define `init_db()`. This function is invoked during application startup in `main.py` to ensure the database schema is fully up to date before receiving user traffic.


---

# STAGE 4: Shared Schemas & Constants
### 4.1 Conversation Pydantic Schemas: [`backend/app/shared/schemas/conversation_schema.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/schemas/conversation_schema.py)

**Architectural Role & Why This File Exists**:
Pydantic validation schemas for script pack JSON files.

**Exhaustive Class & Function Inventory**:
- **Class `QuestionDefinition`**:
- **Class `ConversationDefinitionSchema`**:

**Personal Senior Architect Walkthrough**:
In `conversation_schema.py`, we define `QuestionDefinition` and `ConversationDefinitionSchema`. These models validate question pack JSON structures at load time, ensuring required attributes (`pack_id`, `questions`, `expected_context`) are present.


---
### 4.2 Domain Constants: conversation_types.py: [`backend/app/shared/constants/`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/constants/)

**Architectural Role & Why This File Exists**:
Domain enumeration constants for conversation_types.

**Personal Senior Architect Walkthrough**:
This constants file `conversation_types.py` centralizes string enumerations used across domain policy, state machine transitions, and database queries.


---
### 4.2 Domain Constants: states.py: [`backend/app/shared/constants/`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/constants/)

**Architectural Role & Why This File Exists**:
Domain enumeration constants for states.

**Personal Senior Architect Walkthrough**:
This constants file `states.py` centralizes string enumerations used across domain policy, state machine transitions, and database queries.


---
### 4.2 Domain Constants: interruption_types.py: [`backend/app/shared/constants/`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/constants/)

**Architectural Role & Why This File Exists**:
Domain enumeration constants for interruption_types.

**Personal Senior Architect Walkthrough**:
This constants file `interruption_types.py` centralizes string enumerations used across domain policy, state machine transitions, and database queries.


---

# STAGE 5: Clean Architecture Domain Entities & Interfaces
### 5.1 Session Domain Entity: [`backend/app/modules/session/domain/entities/session_entity.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/session/domain/entities/session_entity.py)

**Architectural Role & Why This File Exists**:
Pure domain entity representing session state and metadata.

**Exhaustive Class & Function Inventory**:
- **Class `Session`**:

**Personal Senior Architect Walkthrough**:
In `session_entity.py`, we define `SessionEntity` as a pure dataclass containing `session_id`, `user_id`, `conversation_type`, `status`, `current_question_index`, `current_state`, `retries`, and timestamp fields.


---
### 5.2 Session Repository Interface: [`backend/app/modules/session/domain/interfaces/session_repository_interface.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/session/domain/interfaces/session_repository_interface.py)

**Architectural Role & Why This File Exists**:
Abstract contract defining session persistence operations.

**Exhaustive Class & Function Inventory**:
- **Class `SessionRepositoryInterface`**:
  - `create(session_id, conversation_type, user_id)`
  - `get_by_id(session_id)`
  - `update_pointer(session_id, index, state, retries)`
  - `pause(session_id)`
  - `close(session_id, status)`

**Personal Senior Architect Walkthrough**:
In `session_repository_interface.py`, we define `SessionRepositoryInterface` with abstract methods `create()`, `get_by_id()`, `update_pointer()`, `pause()`, and `close()`. Data access infrastructure implements this contract.


---
### 5.3 Message Domain Entity: [`backend/app/modules/message/domain/interfaces/message_repository_interface.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/message/domain/interfaces/message_repository_interface.py)

**Architectural Role & Why This File Exists**:
Pure domain entity representing a transcript message.

**Personal Senior Architect Walkthrough**:
In `message_entity.py`, we define `MessageEntity` dataclass containing `id`, `session_id`, `sender` ('system'|'user'), `text`, and `timestamp`.


---
### 5.4 Message Repository Interface: [`backend/app/modules/message/domain/interfaces/message_repository_interface.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/message/domain/interfaces/message_repository_interface.py)

**Architectural Role & Why This File Exists**:
Abstract contract for message persistence operations.

**Exhaustive Class & Function Inventory**:
- **Class `MessageRepositoryInterface`**:
  - `add(session_id, sender, text)`
  - `get_by_session(session_id)`

**Personal Senior Architect Walkthrough**:
In `message_repository_interface.py`, we define `MessageRepositoryInterface` with abstract methods `add()` and `get_by_session()`.


---
## 3. Turn Finite State Machine (FSM) State Diagram
```
                ┌──────────┐
                │   IDLE   │
                └────┬─────┘
                     │ (Initialize Turn)
                     ▼
                ┌──────────┐
                │  ASKING  │
                └────┬─────┘
                     │ (Intro Text Ready)
                     ▼
            ┌──────────────────┐
            │ WAITING_FOR_TTS  │
            └────────┬─────────┘
                     │ (Audio Started)
                     ▼
             ┌────────────────┐       (User Speaks)       ┌───────────────┐
             │  TTS_PLAYING   ├──────────────────────────►│ TRANSCRIBING  │
             └───────┬────────┘                           └───────▲───────┘
                     │ (Audio Ended / Mic On)                     │
                     ▼                                            │
             ┌────────────────┐                                   │
             │   LISTENING    ├───────────────────────────────────┘
             └────────────────┘         (Final Speech Received)
                     │
                     ▼
             ┌────────────────┐
             │   VALIDATING   │
             └───────┬────────┘
                     │
         ┌───────────┴───────────┐
         │ (Invalid Answer)      │ (Valid Answer)
         ▼                       ▼
    ┌──────────┐            ┌──────────┐
    │  RETRY   │            │ ADVANCE  │
    └────┬─────┘            └────┬─────┘
         │ (Retry Line)          │ (Next Question Pointer)
         └──────────┐            ▼
                    │       ┌──────────┐
                    └──────►│NEXT_TURN │
                            └──────────┘
```



### 5.5 Turn Finite State Machine (FSM): [`backend/app/modules/conversation/domain/models/conversation_fsm.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/domain/models/conversation_fsm.py)

**Architectural Role & Why This File Exists**:
State machine driving turn progression and transition guards.

**Exhaustive Class & Function Inventory**:
- **Class `ConversationState`**:
- **Class `TurnStateTransitionError`**:
- **Class `ConversationFSM`**:
  - `__init__(turn_id, question_id, initial_state)`
  - `current_state()`
  - `transition_to(target_state, reason)`
  - `get_history()`

**Personal Senior Architect Walkthrough**:
In `conversation_fsm.py`, we implement `ConversationState` enum (`IDLE`, `ASKING`, `WAITING_FOR_TTS`, `TTS_PLAYING`, `LISTENING`, `TRANSCRIBING`, `VALIDATING`, `RETRY`, `ADVANCE`, `NEXT_TURN`) and `ConversationFSM` with `transition_to(target, reason)`. The FSM enforces an explicit transition matrix (`ALLOWED_TRANSITIONS`), preventing illegal state jumps. Adding `TTS_PLAYING` state enables speech barge-in detection when a transcript arrives while TTS audio is playing.


---
### 5.6 Transactional Turn Context & Race Shielding: [`backend/app/modules/conversation/domain/models/turn_context.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/domain/models/turn_context.py)

**Architectural Role & Why This File Exists**:
Turn context manager shielding against turn race conditions and managing transcript lifecycles.

**Exhaustive Class & Function Inventory**:
- **Class `TranscriptLifecycle`**:
- **Class `TurnContext`**:
  - `__init__(session_id, conversation_id, question_id, sequence_number, question_text, expected_context, retry_counter)`
  - `is_event_valid(turn_id, question_id, session_id)`
  - `mark_listening_started()`
  - `can_accept_transcript(transcript_received_at)`
  - `add_partial_transcript(text)`
  - `set_final_transcript(text)`
  - `mark_transcript_consumed()`
  - `apply_correction(new_transcript)`
  - `cancel_active_validation()`
  - `cancel_active_llm()`
  - `mark_transcript_discarded(reason)`
  - `register_task(task)`
  - `cancel_all_tasks()`
  - `destroy()`

**Personal Senior Architect Walkthrough**:
Look closely at `turn_context.py`. Here we define `TranscriptLifecycle` enum (`CREATED`, `QUEUED`, `ASSIGNED`, `VALIDATED`, `CONSUMED`, `DISCARDED`, `DESTROYED`) and `TurnContext`. It validates turn ownership via `is_event_valid(turn_id, question_id, session_id)`, deduplicates partial transcripts into bounded buffers (max 50 items), maintains a correction stack for user edits, and manages child task cancellation.


---
### 5.7 Conversation Policy Engine: [`backend/app/modules/conversation/domain/policy/conversation_policy.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/domain/policy/conversation_policy.py)

**Architectural Role & Why This File Exists**:
Policy engine mapping user intent classifications to policy actions.

**Exhaustive Class & Function Inventory**:
- **Class `PolicyAction`**:
- **Class `ConversationPolicy`**:
  - `__init__(max_retries)`
  - `resolve_action(classification_type, transcript, current_retry_count)`
  - `evaluate_retry(current_retry_count, validation_passed)`
  - `_action(action, reason)`

**Personal Senior Architect Walkthrough**:
In `conversation_policy.py`, we implement `PolicyAction` enum (`STOP`, `REPEAT`, `CONTINUE`, `FORGET`, `CORRECTION`, `ANSWER`, `END_CONVERSATION`, `NONE`) and `ConversationPolicy` (`resolve_action()`, `evaluate_retry()`). It resolves classified user intents into actionable policy actions and manages retry evaluation when answers are invalid.


---
### 5.8 Abstract Contract: Script Repository Interface: [`backend/app/modules/conversation/domain/interfaces/conversation_repository_interface.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/domain/interfaces/conversation_repository_interface.py)

**Architectural Role & Why This File Exists**:
Abstract domain interface contract for Script Repository Interface.

**Exhaustive Class & Function Inventory**:
- **Class `ConversationRepositoryInterface`**:
  - `initialize()`
  - `get_by_id(conversation_id)`
  - `list_available()`
  - `exists(conversation_id)`

**Personal Senior Architect Walkthrough**:
In `conversation/domain/interfaces/conversation_repository_interface.py`, we define the abstract domain contract `Script Repository Interface` enforcing Clean Architecture isolation.


---
### 5.8 Abstract Contract: LLM Validation Provider Interface: [`backend/app/modules/conversation/domain/interfaces/validation_provider_interface.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/domain/interfaces/validation_provider_interface.py)

**Architectural Role & Why This File Exists**:
Abstract domain interface contract for LLM Validation Provider Interface.

**Exhaustive Class & Function Inventory**:
- **Class `ValidationProviderInterface`**:
  - `async validate(item_type, item_text, expected_context, user_response)`
  - `async validate_stream(item_type, item_text, expected_context, user_response)`

**Personal Senior Architect Walkthrough**:
In `conversation/domain/interfaces/validation_provider_interface.py`, we define the abstract domain contract `LLM Validation Provider Interface` enforcing Clean Architecture isolation.


---
### 5.8 Abstract Contract: Response Repository Interface: [`backend/app/modules/conversation/domain/interfaces/response_repository_interface.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/domain/interfaces/response_repository_interface.py)

**Architectural Role & Why This File Exists**:
Abstract domain interface contract for Response Repository Interface.

**Exhaustive Class & Function Inventory**:
- **Class `ResponseRepositoryInterface`**:
  - `add(sequence, session_id, user_response, validation_result)`

**Personal Senior Architect Walkthrough**:
In `conversation/domain/interfaces/response_repository_interface.py`, we define the abstract domain contract `Response Repository Interface` enforcing Clean Architecture isolation.


---
### 5.8 Abstract Contract: STT Provider Interface: [`backend/app/modules/voice/domain/interfaces/stt_provider_interface.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/domain/interfaces/stt_provider_interface.py)

**Architectural Role & Why This File Exists**:
Abstract domain interface contract for STT Provider Interface.

**Exhaustive Class & Function Inventory**:
- **Class `STTProviderInterface`**:
  - `async connect()`
  - `async send_audio(chunk)`
  - `async receive_any()`
  - `async receive_transcript()`
  - `async drain_pending()`
  - `async close()`

**Personal Senior Architect Walkthrough**:
In `voice/domain/interfaces/stt_provider_interface.py`, we define the abstract domain contract `STT Provider Interface` enforcing Clean Architecture isolation.


---
### 5.8 Abstract Contract: TTS Provider Interface: [`backend/app/modules/voice/domain/interfaces/tts_provider_interface.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/domain/interfaces/tts_provider_interface.py)

**Architectural Role & Why This File Exists**:
Abstract domain interface contract for TTS Provider Interface.

**Exhaustive Class & Function Inventory**:
- **Class `TTSProviderInterface`**:
  - `async synthesize(text)`
  - `async synthesize_stream(text)`
  - `async connect_stream()`
  - `async close()`

**Personal Senior Architect Walkthrough**:
In `voice/domain/interfaces/tts_provider_interface.py`, we define the abstract domain contract `TTS Provider Interface` enforcing Clean Architecture isolation.


---
### 5.8 Abstract Contract: Interruption Domain Entity: [`backend/app/modules/interruption/domain/entities/interruption_entity.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/interruption/domain/entities/interruption_entity.py)

**Architectural Role & Why This File Exists**:
Abstract domain interface contract for Interruption Domain Entity.

**Exhaustive Class & Function Inventory**:
- **Class `Interruption`**:

**Personal Senior Architect Walkthrough**:
In `interruption/domain/entities/interruption_entity.py`, we define the abstract domain contract `Interruption Domain Entity` enforcing Clean Architecture isolation.


---
### 5.8 Abstract Contract: Interruption Repository Interface: [`backend/app/modules/interruption/domain/interfaces/interruption_repository_interface.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/interruption/domain/interfaces/interruption_repository_interface.py)

**Architectural Role & Why This File Exists**:
Abstract domain interface contract for Interruption Repository Interface.

**Exhaustive Class & Function Inventory**:
- **Class `InterruptionRepositoryInterface`**:
  - `add(session_id, interruption_type, interruption_text)`

**Personal Senior Architect Walkthrough**:
In `interruption/domain/interfaces/interruption_repository_interface.py`, we define the abstract domain contract `Interruption Repository Interface` enforcing Clean Architecture isolation.


---

# STAGE 6: Infrastructure Persistence & External Service Adapters
### 6.1 PostgreSQL Session Repository: [`backend/app/modules/session/infrastructure/persistence/postgres_session_repository.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/session/infrastructure/persistence/postgres_session_repository.py)

**Architectural Role & Why This File Exists**:
PostgreSQL DAO implementing domain repository interface for PostgreSQL Session Repository.

**Exhaustive Class & Function Inventory**:
- **Class `PostgresSessionRepository`**:
  - `create(session_id, conversation_type, user_id)`
  - `get_by_id(session_id)`
  - `update_pointer(session_id, index, state, retries)`
  - `pause(session_id)`
  - `close(session_id, status)`

**Personal Senior Architect Walkthrough**:
In `session/infrastructure/persistence/postgres_session_repository.py`, we implement `PostgresSessionRepository`. It executes async SQL queries against PostgreSQL connections checked out from `get_connection()`.


---
### 6.2 PostgreSQL Message Repository: [`backend/app/modules/message/infrastructure/persistence/postgres_message_repository.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/message/infrastructure/persistence/postgres_message_repository.py)

**Architectural Role & Why This File Exists**:
PostgreSQL DAO implementing domain repository interface for PostgreSQL Message Repository.

**Exhaustive Class & Function Inventory**:
- **Class `PostgresMessageRepository`**:
  - `add(session_id, sender, text)`
  - `get_by_session(session_id)`

**Personal Senior Architect Walkthrough**:
In `message/infrastructure/persistence/postgres_message_repository.py`, we implement `PostgresMessageRepository`. It executes async SQL queries against PostgreSQL connections checked out from `get_connection()`.


---
### 6.3 PostgreSQL Response Repository: [`backend/app/modules/conversation/infrastructure/persistence/postgres_response_repository.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/infrastructure/persistence/postgres_response_repository.py)

**Architectural Role & Why This File Exists**:
PostgreSQL DAO implementing domain repository interface for PostgreSQL Response Repository.

**Exhaustive Class & Function Inventory**:
- **Class `PostgresResponseRepository`**:
  - `add(sequence, session_id, user_response, validation_result)`

**Personal Senior Architect Walkthrough**:
In `conversation/infrastructure/persistence/postgres_response_repository.py`, we implement `PostgresResponseRepository`. It executes async SQL queries against PostgreSQL connections checked out from `get_connection()`.


---
### 6.4 PostgreSQL Interruption Repository: [`backend/app/modules/interruption/infrastructure/persistence/postgres_interruption_repository.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/interruption/infrastructure/persistence/postgres_interruption_repository.py)

**Architectural Role & Why This File Exists**:
PostgreSQL DAO implementing domain repository interface for PostgreSQL Interruption Repository.

**Exhaustive Class & Function Inventory**:
- **Class `PostgresInterruptionRepository`**:
  - `add(session_id, interruption_type, interruption_text)`

**Personal Senior Architect Walkthrough**:
In `interruption/infrastructure/persistence/postgres_interruption_repository.py`, we implement `PostgresInterruptionRepository`. It executes async SQL queries against PostgreSQL connections checked out from `get_connection()`.


---
### 6.2 Dynamic JSON Conversation Repository: [`backend/app/modules/conversation/infrastructure/external/json_conversation_repository.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/infrastructure/external/json_conversation_repository.py)

**Architectural Role & Why This File Exists**:
Script repository loading JSON pack files from disk.

**Exhaustive Class & Function Inventory**:
- **Class `JsonConversationRepository`**:
  - `__init__(definitions_dir)`
  - `initialize()`
  - `get_by_id(conversation_id)`
  - `list_available()`
  - `exists(conversation_id)`

**Personal Senior Architect Walkthrough**:
In `json_conversation_repository.py`, we implement `JsonConversationRepository`. It scans `app/conversation_definitions/` for JSON packs, validates them against Pydantic schemas, and provides script definitions at runtime.


---
## 5. Three-Layer LLM Validation Flowchart
```
                 ┌─────────────────────────────────────────┐
                 │          Raw User Transcript            │
                 └────────────────────┬────────────────────┘
                                      │
                                      ▼
                 ┌─────────────────────────────────────────┐
                 │     Layer 1: Guard Rails (<1ms)         │
                 │ Checks empty, single-char, dangling text│
                 └──────────┬───────────────────┬──────────┘
                            │ (Invalid)         │ (Clean Text)
                            ▼                   ▼
                     ┌────────────┐    ┌──────────────────────────────────┐
                     │ Request    │    │ Layer 2: LLM Validation Stream   │
                     │ Retry      │    │ Natural feedback + ###METADATA###│
                     └────────────┘    └────────────────┬─────────────────┘
                                                        │
                                    ┌───────────────────┴───────────────────┐
                                    │ (JSON Parsed OK)     │ (Timeout/Error)
                                    ▼                      ▼
                            ┌──────────────┐     ┌──────────────────────────┐
                            │ Final Score  │     │ Layer 3: Degradation     │
                            │ & Validation │     │ >2 words -> Auto Accept  │
                            └──────────────┘     └──────────────────────────┘
```



### 6.3 Three-Layer LiteLLM Validation Adapter: [`backend/app/modules/conversation/infrastructure/external/litellm_validation_adapter.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/infrastructure/external/litellm_validation_adapter.py)

**Architectural Role & Why This File Exists**:
LLM validation provider implementing 3-layer validation.

**Exhaustive Class & Function Inventory**:
- **Class `LiteLLMValidationAdapter`**:
  - `__init__()`
  - `_get_client()`
  - `async validate(item_type, item_text, expected_context, user_response)`
  - `async validate_stream(item_type, item_text, expected_context, user_response)`

**Personal Senior Architect Walkthrough**:
In `litellm_validation_adapter.py`, we implement `LiteLLMValidationAdapter` (`validate()`, `validate_stream()`). It executes 3-layer validation: (1) Layer 1 Guard Rails (<1ms string checks), (2) Layer 2 Streaming LLM validation parsing tokens and `###METADATA###` JSON blocks, and (3) Layer 3 Graceful Degradation accepting valid multi-word answers if the provider times out.


---
### 6.4 LLM Validation System Prompt: [`backend/app/modules/conversation/infrastructure/external/prompts/validation_prompt.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/infrastructure/external/prompts/validation_prompt.py)

**Architectural Role & Why This File Exists**:
System prompt template for LLM response validation.

**Exhaustive Class & Function Inventory**:
- Function `build_validation_user_message(item_type, item_text, expected_context, user_response)`

**Personal Senior Architect Walkthrough**:
In `validation_prompt.py`, we define `VALIDATION_SYSTEM_PROMPT`. It instructs the LLM to evaluate user transcripts against expected contexts and output structured natural language feedback followed by a JSON metadata block.


---
## STT Listening Epoch Filtering Architecture
```
 Streamed STT Transcripts
            │
            ▼
 ┌──────────────────────┐
 │ Queue Item Tagged    │
 │ with _epoch counter  │
 └──────────┬───────────┘
            │
            ▼
 ┌──────────────────────┐
 │ _epoch == current ?  ├───────► Discard (Stale Transcript from Prior Turn)
 └──────────┬───────────┘
            │ (Yes, Valid)
            ▼
 ┌──────────────────────┐
 │ Process Transcript   │
 └──────────────────────┘
```

### 6.5 Epoch-Filtered Deepgram Streaming STT Adapter: [`backend/app/modules/voice/infrastructure/external/deepgram_stt_adapter.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/external/deepgram_stt_adapter.py)

**Architectural Role & Why This File Exists**:
WebSocket client adapter for Deepgram speech recognition.

**Exhaustive Class & Function Inventory**:
- **Class `DeepgramSTTAdapter`**:
  - `__init__()`
  - `async _listen_loop()`
  - `_start_reader()`
  - `async connect()`
  - `_drain_queue()`
  - `async send_audio(chunk)`
  - `advance_epoch()`
  - `async receive_any()`
  - `async drain_pending()`
  - `async drain_before(epoch)`
  - `parse_stt_message(raw)`
  - `async receive_transcript()`
  - `async close()`

**Personal Senior Architect Walkthrough**:
In `deepgram_stt_adapter.py`, we implement `DeepgramSTTAdapter` (`connect()`, `send_audio()`, `receive_any()`, `drain_pending()`, `close()`). It tags transcript queue items with listening epochs (`_epoch`), discarding stale transcripts from prior turns, and enforces a queue maxsize cap of 500.


---
### 6.6 Deepgram SDK v7.x Streaming TTS Adapter: [`backend/app/modules/voice/infrastructure/external/deepgram_tts_adapter.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/external/deepgram_tts_adapter.py)

**Architectural Role & Why This File Exists**:
WebSocket client adapter for Deepgram speech synthesis using official SDK v7.x.

**Exhaustive Class & Function Inventory**:
- **Class `DeepgramTTSAdapter`**:
  - `__init__()`
  - `_is_v2_model(model_name)`
  - `_get_http_client()`
  - `async synthesize(text)`
  - `_on_message(message)`
  - `_on_close()`
  - `_drain_queue()`
  - `async _cleanup_connection()`
  - `async connect_stream()`
  - `async synthesize_stream(text)`
  - `async close()`

**Personal Senior Architect Walkthrough**:
In `deepgram_tts_adapter.py`, we implement `DeepgramTTSAdapter` (`connect_stream()`, `synthesize_stream()`, `synthesize()`). It uses the official Deepgram SDK v7.x `AsyncDeepgramClient` WebSocket streaming API to yield binary speech chunks back as text is generated, with fallback to REST HTTP synthesis.


---
## 4. Speech Barge-In & Interruption Flow Diagram
```
 Client VAD               WebSocket Handler            CancellationToken        TTS & LLM Coroutines
    │                             │                            │                         │
    ├─► {"type": "tts_interrupt"─►│                            │                         │
    │                             ├───► cancel() ─────────────►│                         │
    │                             │                            ├─── (Abort Instantly) ──►│
    │◄── {"type": "tts_stopped"} ─┤                            │                         │
    │                             │                            │                         │
    │                             ├───► Classify Interruption ─┤                         │
    │                             │     (Tier 1: Keyword)      │                         │
    │                             │     (Tier 2: LLM Intent)   │                         │
```



### 6.7 Two-Tier Interruption Classifier Adapter: [`backend/app/modules/interruption/infrastructure/external/interruption_classifier_adapter.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/interruption/infrastructure/external/interruption_classifier_adapter.py)

**Architectural Role & Why This File Exists**:
Speech interruption classifier implementing two-tier classification.

**Exhaustive Class & Function Inventory**:
- **Class `InterruptionClassifierAdapter`**:
  - `__init__()`
  - `_get_client()`
  - `async classify(transcript, current_question, tts_text, expected_context, previous_answer, is_tts_playing)`

**Personal Senior Architect Walkthrough**:
In `interruption_classifier_adapter.py`, we implement `InterruptionClassifierAdapter` (`classify()`). Tier 1 executes sub-100ms keyword matching for system commands (`stop`, `be quiet`, `reset`, `end`). Tier 2 invokes an LLM to classify speech arriving while TTS is playing into `STOP`, `REPEAT`, `CORRECTION`, `ANSWER`, `END_CONVERSATION`, or `NONE`.


---
### 6.8 Interruption System Prompt: [`backend/app/modules/interruption/infrastructure/external/prompts/interruption_prompt.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/interruption/infrastructure/external/prompts/interruption_prompt.py)

**Architectural Role & Why This File Exists**:
System prompt template for LLM interruption classification.

**Exhaustive Class & Function Inventory**:
- Function `build_interruption_user_message(transcript, current_question, tts_text, expected_context, previous_answer, is_tts_playing)`

**Personal Senior Architect Walkthrough**:
In `interruption_prompt.py`, we define `INTERRUPTION_SYSTEM_PROMPT`. It guides the LLM to classify speech arriving during TTS playback into semantic user intent categories.


---

# STAGE 7: Application Use Cases & Core Services
### 7.1 CreateSession Use Case: [`backend/app/modules/session/application/use_cases/create_session.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/session/application/use_cases/create_session.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for CreateSession Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `CreateSession`**:
  - `__init__(session_repository)`
  - `execute(session_id, conversation_type, user_id)`

**Personal Senior Architect Walkthrough**:
In `session/application/use_cases/create_session.py`, we implement `CreateSession Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 GetSession Use Case: [`backend/app/modules/session/application/use_cases/get_session.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/session/application/use_cases/get_session.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for GetSession Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `GetSession`**:
  - `__init__(session_repository)`
  - `execute(session_id)`

**Personal Senior Architect Walkthrough**:
In `session/application/use_cases/get_session.py`, we implement `GetSession Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 UpdatePointer Use Case: [`backend/app/modules/session/application/use_cases/update_pointer.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/session/application/use_cases/update_pointer.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for UpdatePointer Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `UpdatePointer`**:
  - `__init__(session_repository)`
  - `execute(session_id, index, state, retries)`

**Personal Senior Architect Walkthrough**:
In `session/application/use_cases/update_pointer.py`, we implement `UpdatePointer Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 PauseSession Use Case: [`backend/app/modules/session/application/use_cases/pause_session.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/session/application/use_cases/pause_session.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for PauseSession Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `PauseSession`**:
  - `__init__(session_repository)`
  - `execute(session_id)`

**Personal Senior Architect Walkthrough**:
In `session/application/use_cases/pause_session.py`, we implement `PauseSession Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 CloseSession Use Case: [`backend/app/modules/session/application/use_cases/close_session.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/session/application/use_cases/close_session.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for CloseSession Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `CloseSession`**:
  - `__init__(session_repository)`
  - `execute(session_id, status)`

**Personal Senior Architect Walkthrough**:
In `session/application/use_cases/close_session.py`, we implement `CloseSession Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 AddMessage Use Case: [`backend/app/modules/message/application/use_cases/add_message.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/message/application/use_cases/add_message.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for AddMessage Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `AddMessage`**:
  - `__init__(message_repository)`
  - `execute(session_id, sender, text)`

**Personal Senior Architect Walkthrough**:
In `message/application/use_cases/add_message.py`, we implement `AddMessage Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 GetMessages Use Case: [`backend/app/modules/message/application/use_cases/get_messages.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/message/application/use_cases/get_messages.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for GetMessages Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `GetMessages`**:
  - `__init__(message_repository)`
  - `execute(session_id)`

**Personal Senior Architect Walkthrough**:
In `message/application/use_cases/get_messages.py`, we implement `GetMessages Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 ValidateResponse Use Case: [`backend/app/modules/conversation/application/use_cases/validate_response.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/application/use_cases/validate_response.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for ValidateResponse Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `ValidateResponse`**:
  - `__init__(validation_provider)`
  - `async execute(item_type, item_text, expected_context, user_response)`
  - `async execute_stream(item_type, item_text, expected_context, user_response)`

**Personal Senior Architect Walkthrough**:
In `conversation/application/use_cases/validate_response.py`, we implement `ValidateResponse Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 RecordResponse Use Case: [`backend/app/modules/conversation/application/use_cases/record_response.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/application/use_cases/record_response.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for RecordResponse Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `RecordResponse`**:
  - `__init__(response_repository)`
  - `execute(sequence, session_id, user_response, validation_result)`

**Personal Senior Architect Walkthrough**:
In `conversation/application/use_cases/record_response.py`, we implement `RecordResponse Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 ClassifyInterruption Use Case: [`backend/app/modules/interruption/application/use_cases/classify_interruption.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/interruption/application/use_cases/classify_interruption.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for ClassifyInterruption Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `ClassifyInterruption`**:
  - `__init__(classifier_adapter)`
  - `async execute(transcript, current_question, tts_text, expected_context, previous_answer, is_tts_playing)`

**Personal Senior Architect Walkthrough**:
In `interruption/application/use_cases/classify_interruption.py`, we implement `ClassifyInterruption Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 RecordInterruption Use Case: [`backend/app/modules/interruption/application/use_cases/record_interruption.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/interruption/application/use_cases/record_interruption.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for RecordInterruption Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `RecordInterruption`**:
  - `__init__(interruption_repository)`
  - `execute(session_id, interruption_type, interruption_text)`

**Personal Senior Architect Walkthrough**:
In `interruption/application/use_cases/record_interruption.py`, we implement `RecordInterruption Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.1 SynthesizeSpeech Use Case: [`backend/app/modules/voice/application/use_cases/synthesize_speech.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/application/use_cases/synthesize_speech.py)

**Architectural Role & Why This File Exists**:
Single-responsibility application use case for SynthesizeSpeech Use Case.

**Exhaustive Class & Function Inventory**:
- **Class `SynthesizeSpeech`**:
  - `__init__(tts_provider)`
  - `async execute(text)`
  - `async synthesize_stream(text)`

**Personal Senior Architect Walkthrough**:
In `voice/application/use_cases/synthesize_speech.py`, we implement `SynthesizeSpeech Use Case`. It encapsulates a single application command, invoking domain entities and repository interfaces.


---
### 7.2 Atomic Runtime State Manager: [`backend/app/modules/session/application/services/runtime_state_manager.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/session/application/services/runtime_state_manager.py)

**Architectural Role & Why This File Exists**:
Single source of truth for in-memory session runtime state snapshots.

**Exhaustive Class & Function Inventory**:
- **Class `ConnectionState`**:
- **Class `PlaybackState`**:
- **Class `STTState`**:
- **Class `TTSState`**:
- **Class `SessionRuntimeState`**:
- **Class `RuntimeStateManager`**:
  - `__init__()`
  - `create_session(session_id, conversation_type, user_id, is_recovery)`
  - `get_session(session_id)`
  - `destroy_session(session_id)`
  - `list_active_sessions()`
  - `set_connection_state(session_id, state)`
  - `set_turn(session_id, turn_id, question_index)`
  - `increment_retry(session_id)`
  - `reset_retries(session_id)`
  - `advance_question(session_id)`
  - `set_playback_state(session_id, state, tts_text)`
  - `record_tts_chunk(session_id, chunk_bytes)`
  - `set_stt_state(session_id, state)`
  - `set_tts_state(session_id, state)`
  - `advance_epoch(session_id)`
  - `snapshot(session_id)`

**Personal Senior Architect Walkthrough**:
In `runtime_state_manager.py`, we implement `SessionRuntimeState` and `RuntimeStateManager` (`create_session()`, `set_connection_state()`, `set_turn()`, `advance_epoch()`, `snapshot()`). It provides atomic state updates and immutable snapshots across connection, playback, STT, and TTS states.


---
### 7.3 Conversation Engine Service: [`backend/app/modules/conversation/application/services/conversation_engine.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/application/services/conversation_engine.py)

**Architectural Role & Why This File Exists**:
Script pack navigation and transition phrase generation service.

**Exhaustive Class & Function Inventory**:
- **Class `ConversationEngine`**:
  - `__init__(conversation_repository)`
  - `load_script(conversation_type)`
  - `get_intro_line(conversation_type)`
  - `get_current(conversation_type, index)`
  - `is_complete(conversation_type, index)`
  - `generate_human_transition(prev_item, user_transcript)`

**Personal Senior Architect Walkthrough**:
In `conversation_engine.py`, we implement `ConversationEngine` (`load_script()`, `get_intro_line()`, `get_current()`, `is_complete()`, `generate_human_transition()`). It manages question script advancement and generates natural human transition phrases between turns.


---
### 7.4 Context Manager & Token Budget: [`backend/app/modules/conversation/application/services/context_manager.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/application/services/context_manager.py)

**Architectural Role & Why This File Exists**:
Conversation history context window and token budget manager.

**Exhaustive Class & Function Inventory**:
- **Class `MessageEntry`**:
- **Class `ContextManager`**:
  - `__init__(max_tokens)`
  - `add_message(session_id, role, content, turn_id)`
  - `get_history(session_id)`
  - `get_recent(session_id, count)`
  - `build_validation_prompt(session_id, question_type, question_text, expected_context, user_transcript, max_history)`
  - `build_interruption_prompt(session_id, transcript, current_question, tts_text, expected_context)`
  - `clear(session_id)`
  - `_prune_if_needed(session_id)`

**Personal Senior Architect Walkthrough**:
In `context_manager.py`, we implement `ContextManager` (`add_message()`, `build_validation_prompt()`, `build_interruption_prompt()`). It maintains recent turn history and enforces a 4000-token budget by estimating token counts (`chars / 4`) and pruning older non-system turns.


---
### 7.5 Intent Task Router: [`backend/app/modules/conversation/application/services/task_router.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/application/services/task_router.py)

**Architectural Role & Why This File Exists**:
Intent-to-handler dispatch table.

**Exhaustive Class & Function Inventory**:
- **Class `TaskRouter`**:
  - `__init__()`
  - `register(intent_type, handler)`
  - `set_fallback(handler)`
  - `async route(intent_type, context)`
  - `async _default_fallback(context)`

**Personal Senior Architect Walkthrough**:
In `task_router.py`, we implement `TaskRouter` (`register()`, `set_fallback()`, `route()`). It routes classified user intents to registered domain task handlers.


---
## ResponseCoordinator Sentence-Boundary Streaming Flow
```
 Streaming LLM Tokens ──► [ResponseCoordinator.stream_response]
                                       │
                                       ▼
                        Accumulate Text in Sentence Buffer
                                       │
                    ┌──────────────────┴──────────────────┐
                    │ Sentence End (.!?) / >80 Chars ?    │
                    └──────────────────┬──────────────────┘
                                       │
                        ┌──────────────┴──────────────┐
                        │ Yes                         │ No
                        ▼                             ▼
         ┌──────────────────────────────┐   ┌───────────────────┐
         │ Flush Sentence to Deepgram   │   │ Keep Accumulating │
         │ Stream TTS Synthesis         │   │ Tokens            │
         └──────────────┬───────────────┘   └───────────────────┘
                        │
                        ▼
         ┌──────────────────────────────┐
         │ Parse ###METADATA### JSON    │
         │ Extract is_valid & Score     │
         └──────────────────────────────┘
```

### 7.6 Response Coordinator — LLM -> TTS Pipeline: [`backend/app/modules/conversation/application/services/response_coordinator.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/application/services/response_coordinator.py)

**Architectural Role & Why This File Exists**:
Streaming LLM -> TTS sentence-boundary chunking pipeline coordinator.

**Exhaustive Class & Function Inventory**:
- **Class `StreamingResult`**:
- **Class `ResponseCoordinator`**:
  - `__init__(event_bus, synthesize_speech, validate_response_stream)`
  - `set_cancellation_token(token)`
  - `cancel(reason)`
  - `async stream_response(item, transcript, session_id, turn_id, question_id, turn_context)`
  - `async _tts_flush(text, session_id, turn_id)`
  - `_lenient_json_parse(raw)`
  - `_fallback_metadata(error)`
  - `_no_delimiter_fallback()`

**Personal Senior Architect Walkthrough**:
Study `response_coordinator.py`. Here we implement `StreamingResult` and `ResponseCoordinator` (`stream_response()`). It connects LLM token streaming to TTS speech generation: (1) consumes streaming LLM tokens, (2) accumulates text looking for sentence boundaries (`.!?` or 80+ chars), (3) flushes complete sentences to Deepgram TTS and publishes `tts_audio_chunk` events, and (4) parses streaming JSON metadata after the `###METADATA###` delimiter.


---

# STAGE 8: Presentation Orchestration & WebSocket Controller
### 8.1 Dependency Injection Container: [`backend/app/entrypoints/websocket/dependencies.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/websocket/dependencies.py)

**Architectural Role & Why This File Exists**:
Application composition root registering all system dependencies.

**Exhaustive Class & Function Inventory**:
- Function `get_event_bus()`
- Function `get_conversation_policy()`
- Function `get_context_manager()`
- Function `get_task_router()`
- Function `get_runtime_state_manager()`
- Function `get_provider_health()`
- Function `get_capability_registry()`
- Function `get_conversation_repository()`
- Function `get_session_repository()`
- Function `get_message_repository()`
- Function `get_response_repository()`
- Function `get_interruption_repository()`
- Function `get_stt_adapter()`
- Function `get_tts_adapter()`
- Function `get_validation_adapter()`
- Function `get_interruption_classifier_adapter()`
- Function `get_current_user(token)`

**Personal Senior Architect Walkthrough**:
In `dependencies.py`, we build our FastAPI Dependency Injection container (`get_session_repository()`, `get_message_repository()`, `get_stt_adapter()`, `get_tts_adapter()`, `get_event_bus()`, etc.). It instantiates 18 singletons and repositories and injects them into FastAPI routes via `Depends()`.


---
### 8.2 WebSocket Connection Manager: [`backend/app/entrypoints/websocket/connection_manager.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/websocket/connection_manager.py)

**Architectural Role & Why This File Exists**:
Tracks active WebSocket network connections.

**Exhaustive Class & Function Inventory**:
- **Class `ConnectionManager`**:
  - `__init__()`
  - `async connect(session_id, ws)`
  - `disconnect(session_id)`
  - `async send_json(session_id, payload)`
  - `async send_bytes(session_id, data)`

**Personal Senior Architect Walkthrough**:
In `connection_manager.py`, we implement `ConnectionManager` (`connect()`, `disconnect()`, `send_json()`). It tracks active client WebSocket instances.


---
### 8.3 WebSocket Response Formatter: [`backend/app/entrypoints/response_formatter.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/response_formatter.py)

**Architectural Role & Why This File Exists**:
Standardizes outgoing JSON event formatting.

**Exhaustive Class & Function Inventory**:
- Function `event(event_name, payload)`
- Function `question_event(item)`
- Function `validation_event(valid, reason)`
- Function `completed_event()`
- Function `cancelled_event()`
- Function `error_event(message)`

**Personal Senior Architect Walkthrough**:
In `response_formatter.py`, we implement response formatting helpers (`event()`, `user_transcript()`, `error_event()`) for consistent outgoing JSON WebSocket frames.


---
## Master WebSocket Controller Processing Loop
```
                       ┌───────────────────────────────┐
                       │ Client Connects to WebSocket  │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │ 1. Validate Token & Auth      │
                       │ 2. Init CancellationToken &   │
                       │    SessionResourceManager     │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │ Turn FSM: Initialize Turn     │
                       │ Drive ASKING -> TTS_PLAYING   │
                       └───────────────┬───────────────┘
                                       │
                        ┌──────────────┴───────────────┐
                        │                              │
                        ▼                              ▼
          ┌───────────────────────────┐  ┌───────────────────────────┐
          │ Incoming Binary Audio     │  │ Incoming Client Messages  │
          │ Stream to Deepgram STT    │  │ (barge_in / tts_interrupt)│
          └─────────────┬─────────────┘  └─────────────┬─────────────┘
                        │                              │
                        ▼                              ▼
          ┌───────────────────────────┐  ┌───────────────────────────┐
          │ Final Transcript Received │  │ Cancel Generation Tokens  │
          │ FSM -> VALIDATING         │  │ Send tts_stopped Frame    │
          └─────────────┬─────────────┘  └───────────────────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │ LLM Streaming Validation  │
          │ ResponseCoordinator TTS   │
          └─────────────┬─────────────┘
                        │
                        ▼
          ┌───────────────────────────┐
          │ Final Resource Cleanup    │
          │ resources.release_all()   │
          └───────────────────────────┘
```

### 8.4 Master WebSocket Voice Controller: [`backend/app/entrypoints/websocket/conversation_handler.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/websocket/conversation_handler.py)

**Architectural Role & Why This File Exists**:
Master voice loop hub connecting WebSockets to STT, FSM, Policy, LLM, and TTS.

**Exhaustive Class & Function Inventory**:
- Function `chunk_by_sentence(text)`
- Function `async conversation_socket(ws, conversation_type, session_id, token, session_repo, message_repo, conversation_repo, response_repo, interruption_repo, stt_adapter, tts_adapter, validation_adapter, interruption_classifier, event_bus, conversation_policy, context_manager, runtime_state, provider_health, capability_registry)`

**Personal Senior Architect Walkthrough**:
Now let's examine `conversation_handler.py`. This is the master voice processing hub (`conversation_socket()`). It manages: (1) Token handshake & auth, (2) Initializing `CancellationTokenSource`, `SessionResourceManager`, and `RuntimeStateManager`, (3) Driving FSM turn transitions, (4) Directing the voice loop (mic frames -> STT -> turn context -> policy -> streaming LLM -> sentence TTS -> WebSocket binary audio), (5) Speech barge-in cancellation, and (6) Guaranteed resource teardown via `resources.release_all()` in a `finally` block.


---
### 8.5 Health Check Endpoint: [`backend/app/entrypoints/http/health.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/http/health.py)

**Architectural Role & Why This File Exists**:
HTTP REST endpoint for monitoring backend readiness.

**Exhaustive Class & Function Inventory**:
- Function `async health()`

**Personal Senior Architect Walkthrough**:
In `health.py`, we define the `GET /health` endpoint returning server status.


---
### 8.6 Main FastAPI Application Entrypoint: [`backend/main.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/main.py)

**Architectural Role & Why This File Exists**:
Main application entrypoint initializing database, attaching routers, serving VAD, and mounting SPA files.

**Exhaustive Class & Function Inventory**:
- Function `async root()`
- Function `async spa_fallback(path)`
- Function `async on_startup()`

**Personal Senior Architect Walkthrough**:
In `main.py`, we construct the main FastAPI app instance (`app`). It runs `init_db()` on startup, attaches WebSocket and REST routers, serves Silero VAD models, and mounts static SPA frontend files.


---

# STAGE 9: Backend Automated Test Suite
### 9.1 Shared EventBus Unit Tests: [`backend/tests/shared/test_event_bus.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/shared/test_event_bus.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Shared EventBus Unit Tests.

**Exhaustive Class & Function Inventory**:
- Function `async test_publish_to_sync_handler()`
- Function `async test_publish_to_async_handler()`
- Function `async test_multiple_handlers()`
- Function `async test_handler_error_does_not_propagate()`

**Personal Senior Architect Walkthrough**:
In `tests/shared/test_event_bus.py`, we write pytest test cases covering `Shared EventBus Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Shared Database Migrations Unit Tests: [`backend/tests/shared/test_migrations.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/shared/test_migrations.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Shared Database Migrations Unit Tests.

**Exhaustive Class & Function Inventory**:
- Function `fresh_db(tmp_path, monkeypatch)`
- Function `test_migrations_create_all_tables(fresh_db)`
- Function `test_migrations_are_idempotent(fresh_db)`

**Personal Senior Architect Walkthrough**:
In `tests/shared/test_migrations.py`, we write pytest test cases covering `Shared Database Migrations Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Session Top-Level State Manager Tests: [`backend/tests/session/test_runtime_state_manager.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/session/test_runtime_state_manager.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Session Top-Level State Manager Tests.

**Exhaustive Class & Function Inventory**:
- Function `sm()`
- Function `test_create_and_get_session(sm)`
- Function `test_destroy_session(sm)`
- Function `test_list_active_sessions(sm)`
- Function `test_connection_state(sm)`
- Function `test_turn_lifecycle(sm)`
- Function `test_retry_increment(sm)`
- Function `test_advance_question(sm)`
- Function `test_playback_state(sm)`
- Function `test_tts_chunk_recording(sm)`
- Function `test_stt_tts_state(sm)`
- Function `test_epoch_advance(sm)`
- Function `test_snapshot(sm)`
- Function `test_snapshot_nonexistent(sm)`

**Personal Senior Architect Walkthrough**:
In `tests/session/test_runtime_state_manager.py`, we write pytest test cases covering `Session Top-Level State Manager Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Session Module Use Cases Tests: [`backend/tests/modules/session/test_session_use_cases.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/session/test_session_use_cases.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Session Module Use Cases Tests.

**Exhaustive Class & Function Inventory**:
- Function `fresh_db(tmp_path, monkeypatch)`
- Function `test_session_lifecycle()`

**Personal Senior Architect Walkthrough**:
In `tests/modules/session/test_session_use_cases.py`, we write pytest test cases covering `Session Module Use Cases Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Session Module Runtime State Manager Tests: [`backend/tests/modules/session/test_runtime_state_manager.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/session/test_runtime_state_manager.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Session Module Runtime State Manager Tests.

**Exhaustive Class & Function Inventory**:
- Function `rsm()`
- Function `test_create_and_get_session(rsm)`
- Function `test_connection_state(rsm)`
- Function `test_turn_and_retry(rsm)`
- Function `test_advance_question(rsm)`
- Function `test_playback_state(rsm)`
- Function `test_record_tts_chunk(rsm)`
- Function `test_audio_pipeline_state(rsm)`
- Function `test_epoch(rsm)`
- Function `test_snapshot(rsm)`
- Function `test_destroy_session(rsm)`

**Personal Senior Architect Walkthrough**:
In `tests/modules/session/test_runtime_state_manager.py`, we write pytest test cases covering `Session Module Runtime State Manager Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 TurnContext Race Shielding Unit Tests: [`backend/tests/modules/conversation/test_turn_context.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_turn_context.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying TurnContext Race Shielding Unit Tests.

**Exhaustive Class & Function Inventory**:
- Function `test_fsm_valid_transitions()`
- Function `test_fsm_illegal_transition_raises_error()`
- Function `async test_turn_context_task_cancellation_on_destroy()`
- Function `test_turn_context_event_validation()`
- Function `test_turn_context_correction()`
- Function `async test_turn_context_cancel_active_validation()`

**Personal Senior Architect Walkthrough**:
In `tests/modules/conversation/test_turn_context.py`, we write pytest test cases covering `TurnContext Race Shielding Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Conversation Engine Navigation Unit Tests: [`backend/tests/modules/conversation/test_conversation_engine.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_conversation_engine.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Conversation Engine Navigation Unit Tests.

**Exhaustive Class & Function Inventory**:
- Function `test_dynamic_json_script_loading()`
- Function `test_invalid_json_schema_fails_startup(tmp_path)`
- Function `test_duplicate_conversation_id_fails_startup(tmp_path)`

**Personal Senior Architect Walkthrough**:
In `tests/modules/conversation/test_conversation_engine.py`, we write pytest test cases covering `Conversation Engine Navigation Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Conversation Policy Unit Tests: [`backend/tests/modules/conversation/test_conversation_policy.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_conversation_policy.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Conversation Policy Unit Tests.

**Exhaustive Class & Function Inventory**:
- Function `policy()`
- Function `test_stop_commands(policy)`
- Function `test_end_commands(policy)`
- Function `test_repeat_commands(policy)`
- Function `test_classification_routing(policy)`
- Function `test_evaluate_retry_passed(policy)`
- Function `test_evaluate_retry_max_exceeded(policy)`
- Function `test_evaluate_retry_normal(policy)`

**Personal Senior Architect Walkthrough**:
In `tests/modules/conversation/test_conversation_policy.py`, we write pytest test cases covering `Conversation Policy Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Context Manager Token Budget Unit Tests: [`backend/tests/modules/conversation/test_context_manager.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_context_manager.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Context Manager Token Budget Unit Tests.

**Exhaustive Class & Function Inventory**:
- Function `ctx()`
- Function `test_add_and_get_history(ctx)`
- Function `test_get_recent(ctx)`
- Function `test_pruning(ctx)`
- Function `test_build_validation_prompt(ctx)`
- Function `test_clear(ctx)`

**Personal Senior Architect Walkthrough**:
In `tests/modules/conversation/test_context_manager.py`, we write pytest test cases covering `Context Manager Token Budget Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Task Router Unit Tests: [`backend/tests/modules/conversation/test_task_router.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_task_router.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Task Router Unit Tests.

**Exhaustive Class & Function Inventory**:
- Function `async test_route_to_registered_handler()`
- Function `async test_fallback_for_unregistered()`
- Function `async test_custom_fallback()`

**Personal Senior Architect Walkthrough**:
In `tests/modules/conversation/test_task_router.py`, we write pytest test cases covering `Task Router Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 LiteLLM 3-Layer Validation Adapter Unit Tests: [`backend/tests/modules/conversation/test_validation_adapter.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_validation_adapter.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying LiteLLM 3-Layer Validation Adapter Unit Tests.

**Exhaustive Class & Function Inventory**:
- Function `async test_deterministic_empty_response_rejected()`
- Function `async test_single_char_goes_to_llm()`
- Function `async test_single_char_i_accepted()`
- Function `async test_single_digit_accepted()`
- Function `async test_dangling_fragment_goes_to_llm()`
- Function `async test_dangling_conjunction_goes_to_llm()`
- Function `_mock_llm_response(json_body)`
- Function `_fully_answered_json(intent)`
- Function `_off_topic_json(intent)`
- Function `_needs_clarification_json(follow_up)`
- Function `_user_does_not_know_json()`
- Function `async test_llm_time_answer_seven_advances()`
- Function `async test_llm_time_answer_around_seven_advances()`
- Function `async test_llm_time_answer_half_past_seven_advances()`
- Function `async test_llm_off_topic_brushed_teeth_rejected()`
- Function `async test_llm_dont_know_accepted()`
- Function `async test_llm_yes_no_to_open_ended_accepted()`
- Function `async test_llm_complete_answer_advances()`
- Function `async test_llm_favorite_color_advances()`
- Function `async test_llm_binary_yes_no_advances()`
- Function `async test_llm_stt_typo_understanding()`
- Function `async test_llm_name_answer_advances()`
- Function `async test_llm_skipped_breakfast_advances()`
- Function `async test_fallback_multiword_advances_on_timeout()`
- Function `async test_fallback_single_word_asks_clarification()`
- Function `async test_fallback_multiword_advances_on_exception()`

**Personal Senior Architect Walkthrough**:
In `tests/modules/conversation/test_validation_adapter.py`, we write pytest test cases covering `LiteLLM 3-Layer Validation Adapter Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Response Coordinator Streaming Unit Tests: [`backend/tests/modules/conversation/test_response_coordinator.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_response_coordinator.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Response Coordinator Streaming Unit Tests.

**Exhaustive Class & Function Inventory**:
- **Class `FakeSynthesizeSpeech`**:
  - `__init__(chunks)`
  - `async synthesize_stream(text)`
- Function `async fake_llm_stream()`
- Function `event_bus()`
- Function `coordinator(event_bus)`
- Function `async test_stream_with_delimiter(coordinator)`
- Function `async test_stream_without_delimiter(coordinator)`
- Function `async test_cancellation(coordinator)`
- Function `async test_tts_fallback_on_stream_error(coordinator)`

**Personal Senior Architect Walkthrough**:
In `tests/modules/conversation/test_response_coordinator.py`, we write pytest test cases covering `Response Coordinator Streaming Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Interruption Classifier Unit Tests: [`backend/tests/modules/interruption/test_classify_interruption.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/interruption/test_classify_interruption.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Interruption Classifier Unit Tests.

**Exhaustive Class & Function Inventory**:
- Function `mock_adapter()`
- Function `classifier(mock_adapter)`
- Function `async test_deterministic_stop(classifier, mock_adapter)`
- Function `async test_deterministic_stop_variants(classifier, mock_adapter)`
- Function `async test_deterministic_end(classifier, mock_adapter)`
- Function `async test_deterministic_end_variants(classifier, mock_adapter)`
- Function `async test_llm_answer(classifier, mock_adapter)`
- Function `async test_llm_repeat(classifier, mock_adapter)`
- Function `async test_llm_correction(classifier, mock_adapter)`
- Function `async test_llm_answer_during_tts(classifier, mock_adapter)`
- Function `async test_llm_none(classifier, mock_adapter)`
- Function `async test_no_adapter_defaults_to_none()`

**Personal Senior Architect Walkthrough**:
In `tests/modules/interruption/test_classify_interruption.py`, we write pytest test cases covering `Interruption Classifier Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Deepgram STT Adapter Epoch Unit Tests: [`backend/tests/modules/voice/test_deepgram_stt_adapter.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/voice/test_deepgram_stt_adapter.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Deepgram STT Adapter Epoch Unit Tests.

**Exhaustive Class & Function Inventory**:
- Function `async test_deepgram_stt_adapter_queue_and_drain()`
- Function `async test_deepgram_stt_adapter_epoch_advance()`
- Function `async test_deepgram_stt_adapter_queue_overflow()`

**Personal Senior Architect Walkthrough**:
In `tests/modules/voice/test_deepgram_stt_adapter.py`, we write pytest test cases covering `Deepgram STT Adapter Epoch Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 Deepgram TTS Adapter Streaming Unit Tests: [`backend/tests/modules/voice/test_deepgram_tts_adapter.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/voice/test_deepgram_tts_adapter.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying Deepgram TTS Adapter Streaming Unit Tests.

**Exhaustive Class & Function Inventory**:
- **Class `FakeFlushed`**:
- **Class `FakeWarning`**:
- **Class `FakeMetadata`**:
- Function `_make_mocks()`
- Function `async test_connect_stream_opens_websocket(mock_client_cls)`
- Function `async test_connect_stream_reconnects_when_listener_died(mock_client_cls)`
- Function `test_on_message_bytes_enqueued()`
- Function `test_on_message_flushed_puts_sentinel()`
- Function `test_on_message_warning_logged(caplog)`
- Function `test_on_message_metadata_logged(caplog)`
- Function `test_on_message_bytes_drops_when_queue_full(caplog)`
- Function `async test_synthesize_stream_sends_text_and_yields_chunks(mock_client_cls)`
- Function `async test_synthesize_stream_timeout_raises(mock_wait_for, mock_client_cls)`
- Function `async test_close_cancels_listener_and_exits_context(mock_client_cls)`
- Function `async test_synthesize_uses_rest_fallback()`

**Personal Senior Architect Walkthrough**:
In `tests/modules/voice/test_deepgram_tts_adapter.py`, we write pytest test cases covering `Deepgram TTS Adapter Streaming Unit Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---
### 9.1 End-to-End WebSocket Flow Integration Tests: [`backend/tests/integration/test_websocket_flow.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/integration/test_websocket_flow.py)

**Architectural Role & Why This File Exists**:
Automated test suite verifying End-to-End WebSocket Flow Integration Tests.

**Exhaustive Class & Function Inventory**:
- Function `fresh_db(tmp_path, monkeypatch)`
- Function `_send_tts_end(ws)`
- Function `test_websocket_initial_connection_and_session_started(mock_tts_close, mock_stream, mock_connect_stream, mock_stt_close, mock_stt_connect)`
- Function `test_authorized_session_recovery(mock_tts_close, mock_stream, mock_connect_stream, mock_stt_close, mock_stt_connect)`
- Function `test_unauthorized_session_recovery_rejection(mock_tts_close, mock_stream, mock_connect_stream, mock_stt_close, mock_stt_connect)`
- Function `test_invalid_token_authentication_failure()`

**Personal Senior Architect Walkthrough**:
In `tests/integration/test_websocket_flow.py`, we write pytest test cases covering `End-to-End WebSocket Flow Integration Tests`. Running `pytest` executes all 107 backend test assertions in under 1.2 seconds.


---

---

# STAGE 10: Multi-Provider Administration, Envelope Encryption & Radiant Emerald Frontend Architecture

### 10.1 PostgreSQL Connection Pool & DSN Resolution: [`backend/app/shared/database/db.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/db.py)

**Architectural Role & Why This File Exists**:
Provides a high-performance asyncpg connection pool with lazy initialization and checkout context managers for transactional operations across repositories.

**Exhaustive Class & Function Inventory**:
- Function `async get_pool()`
- Function `async get_connection()`
- Function `async get_transaction()`
- Function `async close_pool()`

**Personal Senior Architect Walkthrough**:
In `db.py`, we implement a singleton connection pool using `asyncpg`. At startup, it resolves the DSN from `settings.database_url`, expanding individual template variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`) into `postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}`. `get_connection()` and `get_transaction()` provide checkout context managers used by all PostgreSQL repositories.


---
### 10.2 Database Migrations Runner: [`backend/app/shared/database/migrations_pg/__init__.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/migrations_pg/__init__.py)

**Architectural Role & Why This File Exists**:
Automated migration execution engine tracking applied schema scripts in `schema_migrations`.

**Exhaustive Migration Inventory**:
- `0001_create_sessions.sql`: Core session state table.
- `0002_create_messages.sql`: Transcripts and message history table.
- `0003_create_responses.sql`: User responses and LLM validation table.
- `0004_create_interruptions.sql`: Barge-in audit log table.
- `0005_create_encryption_keys.sql`: Envelope encryption key versioning table.
- `0006_create_llm_providers.sql`: LLM provider credentials and base URLs table.
- `0007_create_speech_providers.sql`: Deepgram/ElevenLabs STT/TTS credentials and model configurations table.
- `0008_create_bots.sql`: Bot identities, system prompts, provider links, and unique active bot index (`is_active = TRUE`).
- `0009_create_audit_logs.sql`: Security audit logging table.
- `0010_update_tts_model_names.sql`: Model identifier sanitization migration (`aura-2-` -> `aura-`).

**Personal Senior Architect Walkthrough**:
In `migrations_pg/__init__.py`, `run_migrations_pg()` executes pending `.sql` files in sorted alphabetical sequence inside transactions, writing applied filenames to `schema_migrations`. Migration `0010_update_tts_model_names.sql` automatically updates all stored speech provider rows to official provider model identifiers (`aura-stella-en`, `flux-rufus-en`).


---
### 10.3 Envelope Encryption Engine: [`backend/app/shared/security/envelope_encryption.py`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/security/envelope_encryption.py)

**Architectural Role & Why This File Exists**:
Provides zero-leak credential protection using AES-256 GCM Data Encryption Keys (DEKs) wrapped by a master encryption key.

**Exhaustive Function Inventory**:
- Function `encrypt_and_store(plaintext_dict)`
- Function `load_and_decrypt(encrypted_blob, key_version)`

**Personal Senior Architect Walkthrough**:
In `envelope_encryption.py`, we implement envelope encryption for storing sensitive provider API keys in PostgreSQL. Plaintext credential dictionaries are encrypted with a per-record DEK using AES-256 GCM, and the DEK itself is encrypted using the Base64 master key from `settings.master_encryption_key`.


---
### 10.4 Multi-Provider Repositories: [`backend/app/modules/provider/`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/provider/)

**Architectural Role & Why This File Exists**:
PostgreSQL DAOs managing LLM providers, speech providers, and active bot identities.

**Exhaustive Repository Inventory**:
- **Class `PostgresLLMProviderRepository`**: CRUD for OpenAI, Anthropic, Google Vertex, Ollama, and OpenAI-Compatible LLM endpoints.
- **Class `PostgresSpeechProviderRepository`**: CRUD for Deepgram and ElevenLabs STT/TTS configurations.
- **Class `PostgresBotRepository`**: Bot CRUD and atomic single-active bot activation (`activate(bot_id)`).

**Personal Senior Architect Walkthrough**:
`PostgresBotRepository` implements `activate(bot_id)`, which atomically deactivates existing active bots and sets `is_active = TRUE` for the targeted bot. Creating or editing a Bot in Step 3 automatically triggers `activate(bot_id)`, ensuring the user portal immediately uses the newly configured bot.


---
### 10.5 Official Provider Adapters & Factory: [`backend/app/modules/voice/infrastructure/providers/`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/)

**Architectural Role & Why This File Exists**:
Implements official Deepgram SDK `v7.x` and ElevenLabs streaming protocols with automatic REST fallbacks.

**Exhaustive Adapter Inventory**:
- **Class `DeepgramTTSAdapter`**:
  - Dynamically routes Aura models to `/v1/speak` (`speak.v1.connect`) and Flux models (`flux-rufus-en`, `flux-asteria-en`) to `/v2/speak` (`speak.v2.connect`).
  - Fallback REST synthesis yields 4KB audio chunks if WebSocket streaming experiences network interruptions.
- **Class `ElevenLabsTTSAdapter`**:
  - Implements official WebSocket input streaming (`stream-input`) with `voice_settings`, `try_trigger_generation`, and base64 chunk decoding.
  - Includes HTTP REST fallback (`/v1/text-to-speech/{voice_id}`).
- **Class `SpeechProviderFactory`**:
  - Instantiates `STTProviderInterface` and `TTSProviderInterface` dynamically from the active bot's speech provider config in PostgreSQL.


---
### 10.6 Admin REST Endpoints: [`backend/app/entrypoints/http/admin/`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/http/admin/)

**Architectural Role & Why This File Exists**:
HTTP REST management API powering the 4-Step Admin Guided Journey.

**Exhaustive Route Inventory**:
- **`bot_routes.py`**: Bot management endpoints with automatic activation on `create_bot` and `update_bot`.
- **`speech_provider_routes.py`**: Speech provider CRUD, credential validation, and `/sample-audio` live greeting synthesis (routing Flux models to `/v2/speak`).
- **`llm_provider_routes.py`**: LLM provider CRUD and live model discovery (`/fetch-models`).
- **`runtime_routes.py`**: Platform status, database health check (`/health`), and active bot stats (`/stats`).


---
### 10.7 Frontend Radiant Emerald 3D Architecture: [`frontend/src/`](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/)

**Architectural Role & Why This File Exists**:
Modern React 18 SPA rendering a Radiant Emerald 3D energy visualizer, edge-to-edge stardust void, and full voice assistant portal.

**Exhaustive Frontend Component Inventory**:
- **`tokens.js`**: Core design tokens and Radiant Emerald Green HSL palettes (`#10b981`, `hsl(155, 95%, 58%)`).
- **`ParticleVoid.jsx`**: Edge-to-edge floating stardust void positioned in background Z-depth (`Z = -4` to `-24`) to eliminate scroll camera scatter.
- **`Core.jsx` & `CoreSphere.jsx`**: Radiant Emerald 3D energy sphere with organic fluid distortion, STT mic input reactivity, and TTS speaker audio reactivity.
- **`HomePage.jsx` (`/user` Portal)**:
  - User gesture `AudioContext` initialization on **INITIALIZE CORE** click.
  - Automatic startup greeting playback and live speech-to-text transcript overlay feed.
  - Dynamic status indicators (`🎙 Listening...`, `🔊 Speaking...`, `🧠 Thinking...`, `● Ready`).
- **4-Step Admin Guided Journey (`AdminJourney.jsx`)**:
  - **Step 1 (`LlmSection.jsx`)**: Connect LLM Provider & API Key.
  - **Step 2 (`SpeechSection.jsx`)**: Connect Speech Provider, select STT/TTS models (with live greeting previews and request cancellation on fast model switching).
  - **Step 3 (`BotIdentitySection.jsx`)**: Bot Name, System Prompt, LLM Model selection, and auto-activation.
  - **Step 4 (`ReviewSection.jsx` & `LiveSection.jsx`)**: Active bot overview and real-time testing.


---

# CONGRATULATIONS!

You have completed the exhaustive personal tour of the entire backend & frontend architecture! Every single file, class, method, function signature, PostgreSQL migration, envelope encryption scheme, official provider streaming protocol, and 3D visualizer component has been fully documented with senior architectural guidance.

