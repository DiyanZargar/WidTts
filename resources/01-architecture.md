# Real-Time Conversational Widget Platform — Architecture & Design

## 1. System Architecture

```
User → React Widget → WebSocket → FastAPI → Twilio Media Stream → Deepgram STT/TTS → LiteLLM Validation → Conversation Engine → WS Response → Transcript
```

Single entrypoint: `wss://.../ws/{conversation_type}` (or with `?session_id={session_id}` for session recovery). Backend owns session creation, generating a unique UUID. Voice, validation, and persistence are orchestrated server-side per JSON definitions in `app/conversation_definitions/`.

## 2. Architectural Principles

This system follows **Modular Monolith** architecture with **Clean Architecture** principles:

- **Modular Monolith** — the backend is a single deployable unit, organized into self-contained feature modules with clear boundaries. Each module owns its business capability and can be understood independently.
- **Clean Architecture** — every module enforces strict dependency rules: dependencies always point inward toward the Domain layer. The domain never depends on frameworks, databases, or external services.
- **Dependency Injection** — infrastructure implementations are injected into application-layer use cases through abstract interfaces defined in the domain layer.
- **Domain-oriented module boundaries** — modules are organized around business capabilities (session, conversation, voice, interruption, message), not technical roles.

### Dependency Rule

```
Presentation
       ↓
Application
       ↓
  Domain

Infrastructure
       ↑
  Domain
```

Dependencies always point inward. Presentation depends on Application. Application depends on Domain. Infrastructure implements Domain interfaces. Domain depends on nothing.

### Layer Responsibilities

| Layer | Responsibility | Constraints |
|---|---|---|
| **Domain** | Business entities, business rules, interfaces/contracts, value objects | Must not depend on frameworks. Must not depend on infrastructure. Must remain portable and isolated. |
| **Application** | Use cases, orchestration, business workflows, coordination between components | May depend on Domain. Must not directly depend on external systems. |
| **Infrastructure** | Databases, external APIs, storage, third-party integrations | Implements contracts defined by Domain. Should be replaceable with minimal impact. |
| **Presentation** | APIs, WebSockets, request/response handling, serialization | Must not contain business logic. Acts only as an entry point into the application. |

## 3. Module Directory Structure

```
backend/
  app/
    modules/
      session/
        __init__.py
        domain/
          __init__.py
          entities/
            __init__.py
            session_entity.py
          interfaces/
            __init__.py
            session_repository_interface.py
        application/
          __init__.py
          use_cases/
            __init__.py
            create_session.py
            get_session.py
            update_pointer.py
            close_session.py
        infrastructure/
          __init__.py
          persistence/
            __init__.py
            sqlite_session_repository.py
      conversation/
        __init__.py
        domain/
          __init__.py
          entities/
            __init__.py
            question_entity.py
            response_record_entity.py
          interfaces/
            __init__.py
            question_repository_interface.py
            response_repository_interface.py
        application/
          __init__.py
          use_cases/
            __init__.py
            load_script.py
            get_current_question.py
            check_completion.py
            validate_response.py
            record_response.py
          services/
            __init__.py
            conversation_engine.py
        infrastructure/
          __init__.py
          persistence/
            __init__.py
            sqlite_question_repository.py
            sqlite_response_repository.py
          external/
            __init__.py
            litellm_validation_adapter.py
      voice/
        __init__.py
        domain/
          __init__.py
          interfaces/
            __init__.py
            stt_provider_interface.py
            tts_provider_interface.py
        application/
          __init__.py
          use_cases/
            __init__.py
            stream_speech_to_text.py
            synthesize_speech.py
        infrastructure/
          __init__.py
          external/
            __init__.py
            deepgram_stt_adapter.py
            deepgram_tts_adapter.py
      interruption/
        __init__.py
        domain/
          __init__.py
          entities/
            __init__.py
            interruption_entity.py
          interfaces/
            __init__.py
            interruption_repository_interface.py
        application/
          __init__.py
          use_cases/
            __init__.py
            classify_interruption.py
            record_interruption.py
        infrastructure/
          __init__.py
          persistence/
            __init__.py
            sqlite_interruption_repository.py
      message/
        __init__.py
        domain/
          __init__.py
          entities/
            __init__.py
            message_entity.py
          interfaces/
            __init__.py
            message_repository_interface.py
        application/
          __init__.py
          use_cases/
            __init__.py
            add_message.py
        infrastructure/
          __init__.py
          persistence/
            __init__.py
            sqlite_message_repository.py
    shared/
      __init__.py
      database/
        __init__.py
        db.py
        init_db.py
        migrate.py
        migrations/
          __init__.py
          runner.py
          0001_create_sessions_table.sql
          0002_create_messages_table.sql
          0003_create_questions_table.sql
          0004_create_responses_table.sql
          0005_create_interruptions_table.sql
          0006_add_status_index_to_sessions.sql
      config/
        __init__.py
        settings.py
      constants/
        __init__.py
        conversation_types.py
        states.py
        interruption_types.py
      logging/
        __init__.py
        logger.py
      schemas/
        __init__.py
        ws_schema.py
        session_schema.py
        message_schema.py
      exceptions/
        __init__.py
        domain_exceptions.py
    entrypoints/
      __init__.py
      websocket/
        __init__.py
        connection_manager.py
        conversation_handler.py
      http/
        __init__.py
        health.py
      response_formatter.py
    __init__.py
  tests/
    modules/
      session/
        test_session_use_cases.py
      conversation/
        test_conversation_engine.py
        test_validation.py
      interruption/
        test_classify_interruption.py
    shared/
      test_migrations.py
    integration/
      test_websocket_flow.py
  main.py
  requirements.txt
  .env.example
  .gitignore

frontend/
  src/
    components/
      WidgetButton.jsx
      ConversationWindow.jsx
      Transcript.jsx
      SpeakingIndicator.jsx
      ListeningIndicator.jsx
      SessionEndedState.jsx
    hooks/
      useWebSocket.js
      useDeepgramAudio.js
    services/
      websocketService.js
    context/
      ConversationContext.jsx
    pages/
      HomePage.jsx
    utils/
      audioUtils.js
    App.jsx
    main.jsx
  index.html
  package.json
  vite.config.js
  .env.example
  .gitignore
```

### Clean Architecture Mapping

| Clean Architecture Layer | What lives there | Example files |
|---|---|---|
| **Domain** | Entities (dataclasses), abstract repository interfaces (ABC with `@abstractmethod`), value objects, business rules | `session_entity.py`, `session_repository_interface.py` |
| **Application** | Use case classes with `execute()` method, orchestration services | `create_session.py`, `conversation_engine.py` |
| **Infrastructure** | SQLite repository implementations (adapters), Deepgram adapters, Anthropic API client | `sqlite_session_repository.py`, `deepgram_stt_adapter.py` |
| **Presentation** | FastAPI WebSocket handler, HTTP endpoints, response formatters, connection manager | `conversation_handler.py`, `health.py`, `response_formatter.py` |

### Module Ownership

| Module | Business Capability | Entities | Interfaces | Use Cases |
|---|---|---|---|---|
| **session** | Session lifecycle management | `Session` | `SessionRepositoryInterface` | `CreateSession`, `GetSession`, `UpdatePointer`, `CloseSession` |
| **conversation** | Scripted conversation flow, AI validation | `Question`, `ResponseRecord` | `QuestionRepositoryInterface`, `ResponseRepositoryInterface` | `LoadScript`, `GetCurrentQuestion`, `CheckCompletion`, `ValidateResponse`, `RecordResponse` |
| **voice** | Deepgram STT/TTS integration | — | `STTProviderInterface`, `TTSProviderInterface` | `StreamSpeechToText`, `SynthesizeSpeech` |
| **interruption** | Interruption detection and recording | `Interruption` | `InterruptionRepositoryInterface` | `ClassifyInterruption`, `RecordInterruption` |
| **message** | Transcript message persistence | `Message` | `MessageRepositoryInterface` | `AddMessage` |

## 4. WebSocket Lifecycle

```
Client                                Server
  |--- WS connect /ws/{type}/{sid} --->|
  |                                    |-- CreateSession use case (SQLite)
  |<---- event: session_started -------|
  |<---- audio: TTS welcome -----------|
  |<---- event: question(index=0) -----|
  |---- audio chunks (STT stream) ---->|
  |                                    |-- StreamSpeechToText use case -> text
  |                                    |-- ClassifyInterruption use case
  |                                    |-- ValidateResponse use case
  |<---- event: validation_result -----|
  |<---- audio: next TTS or repeat ----|
  |        ... repeats until done ...  |
  |<---- event: session_completed -----|
  |<---- WS close ----------------------|
```

Interruptions (`stop`, `cancel`, `repeat`, correction) are evaluated by the `ClassifyInterruption` use case on every STT-finalized transcript before the normal `ValidateResponse` path runs (see §8).

## 5. Deepgram Integration Flow

1. Backend instantiates a `DeepgramSTTAdapter` (implementing `STTProviderInterface`) per session, opening a streaming STT connection. Credentials never touch the client.
2. Client streams raw audio (Web Audio API → PCM/Opus) over the same WebSocket to the backend as binary frames.
3. Backend forwards binary frames to the Deepgram STT socket via the `StreamSpeechToText` use case; interim results are ignored, only `is_final` transcripts are acted on.
4. Backend sends text to Deepgram TTS via the `SynthesizeSpeech` use case (using `DeepgramTTSAdapter` implementing `TTSProviderInterface`) and relays the returned audio frames to the client as binary WS frames tagged with a JSON header event (`event: tts_audio`).
5. TTS is interruptible: if a `stop`/barge-in event is detected mid-playback, backend sends `event: tts_stop` and the client immediately halts the `<audio>`/AudioBufferSource playback.

## 6. Conversation Engine Design

Conversation definitions are stored as JSON files under `app/conversation_definitions/` (`daily_life.json`, `career_life.json`, `health_wellness.json`, `travel_planner.json`). Questions remain backend-driven/scripted, and JSON acts as the single source of truth. Future conversation packs can be added without code modifications:

```json
{
  "id": 1,
  "title": "Daily Life Companion",
  "sequence": 0,
  "question_type": "question",
  "text": "What should I call you?",
  "expected_context": "a name or preferred nickname",
  "retries_allowed": 3,
  "validation_type": "context_relevance"
}
```

`conversation_engine.py` (application service within the `conversation` module) loads the JSON definition for the requested type at session start, seeds `questions` table rows via `QuestionRepositoryInterface` if not already present, and exposes `get_current(pointer)`, `advance(pointer)`, `is_complete(pointer)`. The engine never mutates order or skips items; it reads pointer state and returns the next item deterministically.

## 7. Conversation Pointer & Session Lifecycle Design

### Session ID Ownership
The **backend generates the `session_id`** (UUID-v4) upon session creation and returns it to the client over WebSocket. The client stores it in `sessionStorage` for reconnecting.

### Session State Machine
```
ACTIVE
   ↓
PAUSED (Browser Closed / Refresh)
   ↓
ACTIVE (Reconnect)
   ↓
COMPLETED
```

### Incomplete vs. Completed Session Rules
- **Incomplete Session + Refresh**:
  1. Backend detects existing session in `PAUSED` or `ACTIVE` state.
  2. Session state, transcript, pointer (`current_question_index`), retries, interruption state, and finalized messages are preserved.
  3. Backend reloads previous transcript and sends it to frontend.
  4. Frontend renders transcript and conversation resumes seamlessly.
- **Completed Session**:
  1. Session marked `COMPLETED` in SQLite; WebSocket closes.
  2. Frontend state cleared. Reopening widget creates a completely new backend-owned session.

## 8. Interruption Handling Design

Every finalized transcript passes through the `ClassifyInterruption` use case first:

| Input pattern | Action |
|---|---|
| `stop` | Emit `tts_stop` immediately, halt current playback, stay on current question, `RecordInterruption` use case logs it |
| `cancel` | `CloseSession` use case marks session `status=cancelled`, close WS, `RecordInterruption` use case logs it |
| `repeat` | Replay current question/instruction audio, no pointer change, `RecordInterruption` use case logs it |
| Correction within same turn (e.g. "No, the answer is X") | Treat the latest utterance in the turn as the operative answer sent to `ValidateResponse` use case; prior utterance in the same turn is discarded from validation but both are stored via `AddMessage` use case |

All four types are written to the `interruptions` table via `RecordInterruption` with `interruption_type` and raw `interruption_text`.

## 9. SQLite Schema

```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    conversation_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    current_question_index INTEGER NOT NULL DEFAULT 0,
    current_state TEXT NOT NULL DEFAULT 'welcoming',
    retries INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    sender TEXT NOT NULL CHECK (sender IN ('system','user')),
    text TEXT NOT NULL,
    timestamp TEXT NOT NULL
);

CREATE TABLE questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_type TEXT NOT NULL,
    question_text TEXT NOT NULL,
    expected_context TEXT NOT NULL,
    sequence INTEGER NOT NULL
);

CREATE TABLE responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES questions(question_id),
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    user_response TEXT NOT NULL,
    validation_result TEXT NOT NULL CHECK (validation_result IN ('valid','invalid'))
);

CREATE TABLE interruptions (
    interruption_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    interruption_type TEXT NOT NULL CHECK (interruption_type IN ('stop','cancel','repeat','correction')),
    interruption_text TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

## 10. FastAPI Endpoint Structure

```
GET  /health                                  -- liveness check (entrypoints/http/)
WS   /ws/{conversation_type}/{session_id}     -- single entrypoint (entrypoints/websocket/)
```

No REST endpoints for conversation data are exposed (no report generation, no analytics API), per scope. `session_id` is generated by backend (UUID-v4) upon session creation and returned to client for reconnect handling.

## 11. React Component Hierarchy

```
App
 └─ HomePage
     └─ ConversationContext.Provider
         └─ WidgetButton
             └─ ConversationWindow (rendered when open)
                 ├─ Transcript
                 ├─ SpeakingIndicator
                 ├─ ListeningIndicator
                 └─ SessionEndedState (rendered when status=completed|cancelled)
```

## 12. State Management Approach

`ConversationContext` (React Context + `useReducer`) holds: `isOpen`, `sessionId`, `status`, `transcript[]`, `isSpeaking`, `isListening`. `useWebSocket` dispatches reducer actions on every inbound WS event. No external state library — scope does not warrant Redux/Zustand.

## 13. Session Lifecycle

```
ACTIVE (Connecting / Welcoming / Asking / Listening / Validating)
   │
   ├── Browser Close / Refresh ──> PAUSED (Preserved in SQLite)
   │                                   │
   │── User Reconnect ─────────────────┘ (Backend loads transcript & resumes pointer)
   │
   └── Question Script Finished ──> COMPLETED (WebSocket closes, clear frontend state)
```

Clicking widget after session is `COMPLETED` creates a brand-new backend-owned session.

## 14. Data Flow Diagram

```
User → React Widget → WebSocket → FastAPI → Twilio Media Stream → Deepgram STT/TTS → LiteLLM Validation → Conversation Engine → WS Response → Transcript
```

## 15. LiteLLM Validation Flow

```
FastAPI → LiteLLM → Validation Result
```

```python
# Conceptual only — see 02-backend-code.md for implementation
result = validate_response_use_case.execute(
    expected_context=current_item.expected_context,
    user_response=transcript_text,
    item_type=current_item.type,  # "question" | "instruction"
)
# result: { "valid": bool, "reason": str }
```

LiteLLM is used internally for:
- Context validation (topical relevance to expected context).
- Completion detection (for instruction items).
- Interruption & correction detection.

LiteLLM never generates questions, alters sequence order, skips items, or creates summaries/reports.

## 16. Error Handling Strategy

| Failure | Handling |
|---|---|
| Deepgram STT connection drop | Retry connect once; on second failure, TTS: "I couldn't hear you, let's try again," repeat current item |
| Deepgram TTS failure | Send text-only WS event as fallback so transcript still updates; log error |
| LiteLLM validation service timeout/error | Treat as `invalid` with reason `"validation_unavailable"`, repeat item, increment retries, cap at 3 then escalate to `cancelled` with an explanatory TTS message |
| WS disconnect mid-session | Session set to `PAUSED` in SQLite; on reconnect with same `session_id`, backend reloads transcript and pointer |
| Malformed client frame | Ignore frame, log, no pointer mutation |

## 17. Backend Implementation Phases

1. `shared/database/` + `shared/config/` — database connection, migrations, settings.
2. `modules/session/` — Session entity, repository interface, SQLite adapter, use cases (Backend-owned UUID session creation & PAUSED/ACTIVE state machine).
3. `modules/message/` — Message entity, repository interface, SQLite adapter, `AddMessage` use case (Finalized message & transcript recovery).
4. `modules/conversation/` — Question/ResponseRecord entities, repository interfaces, SQLite adapters, JSON definition loader (`app/conversation_definitions/`), `LoadScript`/`GetCurrentQuestion`/`CheckCompletion` use cases.
5. `modules/voice/` — STT/TTS provider interfaces, Deepgram adapters, `StreamSpeechToText`/`SynthesizeSpeech` use cases.
6. `modules/interruption/` — Interruption entity, repository interface, SQLite adapter, `ClassifyInterruption`/`RecordInterruption` use cases.
7. `modules/conversation/` (continued) — `ValidateResponse`/`RecordResponse` use cases, LiteLLM validation adapter (`litellm_validation_adapter.py`).
8. `entrypoints/` — connection manager, conversation handler (wires all modules together), HTTP health endpoint, response formatter.
9. `main.py` — app assembly, startup lifecycle.
10. `shared/schemas/` + `shared/constants/` + `shared/logging/` — supporting utilities.

## 18. Frontend Implementation Phases

1. `context/ConversationContext.jsx` — state shape + reducer.
2. `services/websocketService.js` + `hooks/useWebSocket.js`.
3. `hooks/useDeepgramAudio.js` + `utils/audioUtils.js` — mic capture, playback, barge-in stop.
4. `components/WidgetButton.jsx`, `ConversationWindow.jsx`.
5. `components/Transcript.jsx`, `SpeakingIndicator.jsx`, `ListeningIndicator.jsx`, `SessionEndedState.jsx`.
6. `pages/HomePage.jsx` + `App.jsx` wiring.

## 19. Testing Strategy

- **Unit (backend):** use case `execute()` methods with mocked repository interfaces; conversation_engine pointer transitions; interruption classification; each module tested in isolation by injecting mock implementations of domain interfaces.
- **Unit (frontend):** reducer action transitions; `useWebSocket` event-to-dispatch mapping (mock WS).
- **Integration (backend):** full WS session against mocked Deepgram adapters and mocked AI validation, asserting correct SQLite rows for a scripted 3-question run including one invalid retry and one `repeat` interruption.
- **Manual/E2E:** real Deepgram sandbox key, verify barge-in stop latency and refresh-resume behavior.
- **Regression:** fixed transcript fixtures per interruption type (`stop`, `cancel`, `repeat`, correction) run through `ClassifyInterruption` use case on every change to its classification rules.

## 20. Project Completion Roadmap

| Milestone | Scope |
|---|---|
| M1 | Shared infrastructure (database, config) + session module + message module |
| M2 | Conversation module with all 4 scripts loaded, pointer logic verified |
| M3 | Voice module with Deepgram STT/TTS adapters, real audio round-trip |
| M4 | Conversation module validation: ValidateResponse use case wired to Anthropic client, retries/invalid path verified |
| M5 | Interruption module (`stop`/`cancel`/`repeat`/correction) verified against fixtures |
| M6 | Entrypoints: WebSocket handler + HTTP health, full backend assembled |
| M7 | Frontend widget complete, refresh-resume verified |
| M8 | Integration test suite green, manual E2E pass on Deepgram sandbox |

Excluded by explicit scope: authentication/authorization, analytics, dashboards, report/summary generation, multi-service infra (queues, Docker/Kubernetes, additional databases), session recovery across true completions, AI-driven question generation.

---

## 21. Live Transcript Overlay

### 21.1 Scope Constraint

The transcript overlay is **strictly a presentation-layer addition**. It:
- Uses the existing single WebSocket connection — no additional channels.
- Reads backend events already emitted — no backend logic changes.
- Stores only finalized text — uses the existing `messages` SQLite table.
- Never influences AI decisions, conversation order, session state, pointers, or interruption handling.

### 21.2 Overlay Architecture

```
┌─────────────────────────────────────────┐
│  ConversationWindow                      │
│  ┌───────────────────────────────────┐  │
│  │  Title: "AI Companion"            │  │
│  │  ─────────────────────────────── │  │
│  │  TRANSCRIPT OVERLAY               │  │
│  │  (plain text, max 4–6 lines)      │  │
│  │                                   │  │
│  │  Hello, welcome.       ← fading   │  │
│  │  My name is Diyan.     ← fading   │  │
│  │  What should I call you?          │  │   ← speaking (highlighted)
│  │  Diyan.                           │  │
│  │  How are you feeling today?  ←──  │  │   ← auto-scroll keeps latest visible
│  └───────────────────────────────────┘  │
│  SpeakingIndicator  ListeningIndicator  │
└─────────────────────────────────────────┘
```

No borders, no bubbles, no avatars, no timestamps, no grouping, no history panel.

### 21.3 New WebSocket Events (Backend → Frontend)

The conversation handler emits two additional JSON events over the existing WebSocket connection. No new WS connections are created.

| Event | Payload | When emitted |
|---|---|---|
| `assistant_transcript` | `{ "text": str, "is_speaking": bool }` | Immediately before TTS audio bytes are sent (`is_speaking: true`); after audio ends (`is_speaking: false`) |
| `user_partial_transcript` | `{ "text": str }` | On every non-final Deepgram STT result |

Existing events reused for transcript lifecycle:

| Existing Event | Transcript Action |
|---|---|
| `session_started` | Initialize overlay empty |
| `tts_audio_meta` | Append assistant line, mark highlighted |
| `tts_stop` (barge-in) | Remove highlight immediately |
| `validation_result` | No overlay change |
| `session_completed` | Clear overlay, close WS |
| `session_cancelled` | Clear overlay, close WS |

`user_final_transcript` is derived client-side: when the first `validation_result` event arrives after a `user_partial_transcript`, the partial line is replaced by the finalized user text already stored in the event context.

### 21.4 Frontend Transcript State Shape

The `ConversationContext` reducer extends with three new fields:

```js
transcriptLines:      [],     // { id, speaker, text, isHighlighted } — max displayed: 4–6
partialTranscript:    "",     // current partial STT text (not persisted)
isAssistantSpeaking:  false,  // drives highlight on current assistant line
```

Actions added to the reducer:

| Action | Effect |
|---|---|
| `APPEND_TRANSCRIPT_LINE` | Push `{ id, speaker, text, isHighlighted: false }` |
| `SET_PARTIAL_TRANSCRIPT` | Replace `partialTranscript` string |
| `CLEAR_PARTIAL_TRANSCRIPT` | Set `partialTranscript` to `""` |
| `SET_ASSISTANT_HIGHLIGHT` | Toggle `isHighlighted` on last assistant line |
| `RESET_TRANSCRIPT` | Set `transcriptLines: []`, `partialTranscript: ""` |

### 21.5 Transcript Rendering Rules

**Assistant lines:**
- Appended immediately when `tts_audio_meta` event is received (before audio plays).
- Line is highlighted (`font-weight: 500`, subtle color shift) while `isAssistantSpeaking: true`.
- Highlight removed when TTS audio ends or `tts_stop` fires.

**User lines:**
- `partialTranscript` renders as a transient line below all finalized lines.
- On `user_final_transcript` (first finalized STT result), `partialTranscript` is cleared and the final text is appended as a permanent `transcriptLines` entry.
- Interruptions (`stop`, `cancel`, `repeat`, `correction`) do not suppress the display of the user's spoken text — it is always appended once finalized.

**Visibility window:**
- A maximum of 4–6 lines are visible at any time.
- Older lines fade (CSS `opacity` + `transition`) as new lines push them up.
- Auto-scroll via `useEffect` + `scrollTop = scrollHeight` on every `transcriptLines` change.

### 21.6 SQLite Persistence Behavior

No schema changes required. Existing `messages` table behavior:

| Text type | Persisted? | Table | Sender value |
|---|---|---|---|
| Assistant question/instruction text | Yes (existing) | `messages` | `"system"` |
| User finalized response | Yes (existing) | `messages` | `"user"` |
| User partial transcript | **No** | — | — |
| Interruption text | Yes (existing) | `interruptions` | — |
| Corrections | Yes (existing) | `messages` + `interruptions` | `"user"` |

### 21.7 Transcript Lifecycle

```
widget open
    │
    ▼
RESET_TRANSCRIPT (transcriptLines=[], partialTranscript="")
    │
    ▼
session_started event received
    │
    ▼
tts_audio_meta → APPEND_TRANSCRIPT_LINE (assistant intro)
                → SET_ASSISTANT_HIGHLIGHT true
    │
    ▼
binary audio plays
    │
    ▼
audio ends → SET_ASSISTANT_HIGHLIGHT false
    │
    ▼
user speaks → user_partial_transcript → SET_PARTIAL_TRANSCRIPT (transient)
    │
    ▼
STT finalized → CLEAR_PARTIAL_TRANSCRIPT
              → APPEND_TRANSCRIPT_LINE (user final)
    │
    ▼
    ... loop per question ...
    │
    ▼
session_completed / session_cancelled → RESET_TRANSCRIPT
```

### 21.8 End-to-End Transcript Sequence

```
Client                          Server                    Deepgram
  │                               │                          │
  │── WS connect ───────────────> │                          │
  │<─ session_started ────────────│                          │
  │<─ tts_audio_meta("Welcome")───│                          │
  │  APPEND assistant line        │                          │
  │  highlight ON                 │                          │
  │<─ [binary audio] ─────────────│<── TTS audio bytes ──────│
  │  audio plays                  │                          │
  │  audio ends → highlight OFF   │                          │
  │<─ tts_audio_meta("Q1") ───────│                          │
  │  APPEND assistant line        │                          │
  │  highlight ON                 │                          │
  │<─ [binary audio] ─────────────│                          │
  │  user speaks                  │                          │
  │── [binary audio chunks] ─────>│──── stream to Deepgram ─>│
  │<─ user_partial_transcript ────│<── interim result ────────│
  │  SET_PARTIAL "Mang..."        │                          │
  │<─ user_partial_transcript ────│<── interim result ────────│
  │  SET_PARTIAL "Mango"          │                          │
  │                               │<── is_final result ───────│
  │                               │  add_message("user","Mango")
  │  CLEAR_PARTIAL                │                          │
  │  APPEND user "Mango"          │                          │
  │<─ validation_result ──────────│                          │
  │<─ tts_audio_meta("Q2") ───────│                          │
  │  APPEND assistant line        │                          │
  │         ...                   │                          │
  │<─ session_completed ──────────│                          │
  │  RESET_TRANSCRIPT             │                          │
  │  WS closes                    │                          │
```

### 21.9 Minimal UI Wireframe (Text Representation)

```
┌──────────────────────────┐
│  AI Companion            │
│                          │
│  Hello, welcome.         │   ← fading (opacity 0.4)
│  What should I call you? │   ← highlighted while speaking
│  Diyan.                  │
│  How are you feeling?    │
│  Pretty good.            │   ← latest, full opacity
│  Mang_                   │   ← partial (italic, transient)
│                          │
│  ● Speaking  ◎ Listening │
└──────────────────────────┘
```

No borders. No bubbles. No icons other than minimal status dots already in `SpeakingIndicator` / `ListeningIndicator`. Maximum 4–6 lines visible. Smooth fade for older lines. Auto-scroll always follows the latest line.

### 21.10 Component Impact Summary

| Component / File | Change |
|---|---|
| `context/ConversationContext.jsx` | Extend state + reducer with 3 new fields and 5 new actions |
| `hooks/useTranscript.js` | **New file** — encapsulates transcript state logic |
| `components/TranscriptOverlay.jsx` | **New file** — renders lines + partial line + auto-scroll |
| `components/ConversationWindow.jsx` | Include `TranscriptOverlay` beneath the widget title |
| `services/websocketService.js` | Pass through `user_partial_transcript` to `onEvent` (no logic change) |
| `hooks/useWebSocket.js` | Dispatch `SET_PARTIAL_TRANSCRIPT` on `user_partial_transcript` event |
| Backend `conversation_handler.py` | Emit `user_partial_transcript` on non-final Deepgram results |

No new files in backend. No new database tables. No schema changes.
