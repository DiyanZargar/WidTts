# widTTS → LiveKit Transport Migration

Full implementation plan for migrating widTTS from custom WebSocket/audio transport to LiveKit, per the SDD, SDD Extension, and Zero Hardcoding Policy.

> [!IMPORTANT]
> This is a major architectural migration touching **every layer** of the stack. The migration replaces ~35 files, deletes ~15 modules, adds ~10 new files, and results in a net reduction in repository size. It follows the SDD's mandated phase order strictly.

---

## User Review Required

> [!WARNING]
> **Three SDD Decision Points confirmed (§0)** — please flag now if any are wrong:
> 1. LiveKit owns realtime speech processing outright (STT, TTS, VAD execution via official plugins). widTTS authors only the `WidTTSLLMBridge`.
> 2. Client-side VAD is deleted — `livekit-plugins-silero` runs server-side.
> 3. LiveKit deployment target is configuration-only (`server_url` + API key/secret), not a code branch.

> [!CAUTION]
> **Breaking changes** this migration introduces:
> - The `/ws/{conversation_type}` WebSocket endpoint is **deleted**. Replaced by `/realtime/token` + LiveKit room connection.
> - All frontend audio pipeline code (AudioPipeline, StreamingAudioPlayer, VAD, AudioWorklets, etc.) is **deleted**.
> - The `@ricky0123/vad-web`, `onnxruntime-web`, and `deepgram-sdk` packages are **removed**.
> - New `realtime_runtime_config` table and admin panel required.

---

## Open Questions

> [!IMPORTANT]
> **LiveKit local development setup**: The SDD specifies that a local LiveKit OSS server should be documented for development. Do you have a preference for how to run it locally? (Docker is the standard approach: `docker run -d --rm -p 7880:7880 -p 7881:7881 livekit/livekit-server --dev`). I'll include this in the developer guide.

> [!IMPORTANT]
> **Admin UI for Realtime Runtime Config (§8)**: The SDD says to wire it "wherever the existing journey handles infrastructure-level settings" with the label "Realtime Connection" (no LiveKit terminology). Currently, [AdminJourney](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/components/journey/AdminJourney.jsx) handles the admin experience. I'll add a new configuration pane in the same glass-pane visual style. Confirm this is the right placement.

---

## Proposed Changes

The migration follows the SDD's mandated phase order. I've mapped every SDD phase to concrete file-level changes.

---

### Phase 1 — Repository Audit (Documentation Only)

Generate the audit artifacts before touching any code. These will be written to `resources/docs/` as markdown.

#### [NEW] [repository_audit.md](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/resources/docs/repository_audit.md)
Architecture Report, Dependency Graph, Module Graph, Directory Graph, Dead Code Report, Duplicate Responsibility Report, Empty Folder Report, Misplaced File Report, Infrastructure Ownership Report. Every module categorized as KEEP/DELETE/MOVE/MERGE/REFACTOR.

---

### Phase 2 — Responsibility Migration Matrix (Documentation Only)

#### [NEW] [migration_matrix.md](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/resources/docs/migration_matrix.md)
File-level matrix matching SDD §3. Every responsibility gets exactly one owner.

---

### Phase 3 — Database Migration

#### [NEW] [0011_create_realtime_runtime_config.sql](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/database/migrations_pg/0011_create_realtime_runtime_config.sql)
Creates `realtime_runtime_config` table per SDD §8. Envelope-encrypted API key/secret, configurable TTL and sample rate, singleton pattern.

---

### Phase 4 — Backend: LiveKit Runtime Integration

This is the core of the migration. New files in `infrastructure/`, deletions of old transport/STT/TTS code.

---

#### Backend — New Files

##### [NEW] `backend/app/modules/voice/infrastructure/external/widtts_llm_bridge.py`
The custom LLM bridge per SDD §4. Implements `livekit.agents.llm.LLM`. Receives committed transcripts from LiveKit, routes through `ConversationPolicy` for intent classification (STOP/REPEAT/CORRECTION/END), then delegates to existing `LiteLLMConversationAdapter`-equivalent logic for streaming LLM responses. This is the **only** file authoring a LiveKit plugin interface.

##### [NEW] `backend/app/modules/voice/infrastructure/external/speech_plugin_factory.py`
Replaces the old [provider_factory.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/provider_factory.py). Reads `speech_providers` config and constructs official LiveKit plugin instances (`deepgram.STT`, `deepgram.TTS`, `elevenlabs.STT`, `elevenlabs.TTS`). Raises `UnsupportedProviderError` for unknown types.

##### [NEW] `backend/app/modules/voice/infrastructure/external/livekit_session_adapter.py`
Manages the full session lifecycle per SDD Extension:
- Configuration snapshot capture (immutable for session duration)
- Plugin instantiation (STT, TTS, VAD, LLM bridge — all per-session, never shared)
- `AgentSession` creation and `session.start(room=room)`
- Deterministic cleanup: destroy `AgentSession`, destroy plugins, release memory, persist analytics/metadata, flush logs
- Structured event emission for every lifecycle stage
- Failure handling for every infrastructure dependency

##### [NEW] `backend/app/modules/voice/infrastructure/persistence/postgres_realtime_config_repository.py`
Repository for `realtime_runtime_config` table. `get_active()`, `upsert()`, `test_connection()`.

##### [NEW] `backend/app/entrypoints/http/realtime_token_routes.py`
New runtime route: `POST /realtime/token`. Mints a LiveKit `AccessToken` (via `livekit-api`) scoped to a per-session room. Returns `{token, room_name, server_url}`. Called by the frontend before `begin()`.

##### [NEW] `backend/app/entrypoints/http/admin/realtime_config_routes.py`
Admin routes per SDD §8:
- `GET /admin/api/realtime-runtime`
- `PUT /admin/api/realtime-runtime`
- `POST /admin/api/realtime-runtime/test`

##### [NEW] `backend/app/shared/events/structured_events.py`
Structured event emitter covering all SDD Extension observability requirements (Application Startup/Shutdown, Room Created/Joined/Closed, Session Started/Completed/Failed, Plugin Created/Destroyed, LLM/STT/TTS lifecycle events, etc.). Every event includes timestamp, session_id, bot_id, runtime_id, correlation_id, duration where applicable. Never logs secrets.

---

#### Backend — Modified Files

##### [MODIFY] [main.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/../main.py)
- Add startup validation per SDD Extension: Database Connectivity, Migration State, Master Encryption Key, Application Secret, Runtime Configuration, Speech Provider Configuration, Active Bot, LLM Configuration.
- If any validation fails, startup must fail with a clear error.
- Register the new `realtime_token_routes` router.
- Register the new `realtime_config_routes` admin router.
- Remove static file serving for VAD/ONNX assets (`silero_vad_v5.onnx`, `vad.worklet.bundle.min.js`, `worklet.js`, `ort-wasm/`, `vad/`).

##### [MODIFY] [dependencies.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/websocket/dependencies.py)
- Remove imports of `STTProviderInterface`, `TTSProviderInterface`, old `SpeechProviderFactory`.
- Remove `build_speech_adapters_from_bot()` (replaced by `SpeechPluginFactory` inside `LiveKitSessionAdapter`).
- Keep `build_llm_config_from_bot()`, `get_bot_repository()`, `get_speech_provider_repository()`, all other business-logic dependencies.
- Remove capability registry entries for now-deleted capabilities (`streaming_stt`, `streaming_tts`, `rnnoise`, `browser_dsp`, `silero_vad`, `barge_in`, `audio_metrics`, `audio_health_monitor`).

##### [MODIFY] [admin/__init__.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/http/admin/__init__.py)
- Add `realtime_config_routes` router.

##### [MODIFY] [runtime_state_manager.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/session/application/services/runtime_state_manager.py)
- Simplify: remove `STTState`, `TTSState`, `PlaybackState`, `ConnectionState` enums and their tracking fields that duplicated audio pipeline state (now owned by LiveKit).
- Keep: `session_id`, `conversation_type`, `user_id`, `current_turn_id`, `current_question_index`, `retry_count`, `is_recovery`, `is_destroyed`, lifecycle methods.
- The `listening_epoch`, `tts_chunks_received`, `tts_bytes_received`, `current_tts_text`, `websocket_id` fields are removed (LiveKit owns this state now).

##### [MODIFY] [conversation_policy.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/domain/policy/conversation_policy.py)
- **No changes** — pure business logic, unchanged per SDD §7. Invoked from `WidTTSLLMBridge.chat()`.

##### [MODIFY] [response_coordinator.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/application/services/response_coordinator.py)
- Delete `_tts_flush()` method and all TTS-related logic (sentence-boundary chunking for TTS flush). LiveKit's pipeline consumes `WidTTSLLMBridge.chat()`'s streamed `ChatChunk`s directly.
- Keep `stream_bot_response()` logic (the LLM call + text assembly) but move it into `WidTTSLLMBridge.chat()`. After the move, this file can be deleted if nothing else references it, or kept for `stream_response()` (the `###METADATA###`-aware path) if still used.
- Actually: per the SDD, `ResponseCoordinator`'s TTS-flush logic is redundant but the metadata-free text streaming is kept inside `WidTTSLLMBridge.chat()`. The entire `ResponseCoordinator` can be simplified or its remaining logic merged into the bridge.

##### [MODIFY] [conversation_fsm.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/domain/models/conversation_fsm.py)
- Remove transport-adjacent states: `WAITING_FOR_TTS`, `TTS_PLAYING`, `LISTENING`, `TRANSCRIBING` (per SDD §3 note).
- Keep business-level states: `IDLE`, `ASKING`, `VALIDATING`, `RETRY`, `ADVANCE`, `NEXT_TURN`.
- Update `ALLOWED_TRANSITIONS` map accordingly.

##### [MODIFY] [turn_context.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/domain/models/turn_context.py)
- Remove `listening_epoch`, `advance_epoch()`, `drain_before()`, STT adapter references.
- Remove `TranscriptLifecycle` stages that tracked transport-level transcript flow (`QUEUED`, `DISCARDED` based on epoch).
- Keep: `turn_id`, `session_id`, `sequence_number`, `retry_counter`, `question_text`, `expected_context`, `fsm`, `destroy()`, business-level transcript tracking.

##### [MODIFY] [requirements.txt](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/requirements.txt)
- Add: `livekit-api`, `livekit-agents`, `livekit-plugins-deepgram`, `livekit-plugins-elevenlabs`, `livekit-plugins-silero`
- Remove: `deepgram-sdk` (no longer directly called), `websockets` (if only used for the old raw WS transport)

---

#### Backend — Deleted Files

##### [DELETE] [connection_manager.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/websocket/connection_manager.py)
Raw WebSocket connection manager. LiveKit room/participant lifecycle replaces this entirely.

##### [DELETE] [conversation_handler.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/websocket/conversation_handler.py)
The entire 417-line WebSocket endpoint handler. Bot-loading/config logic is preserved — moved into `LiveKitSessionAdapter`. The raw WebSocket receive loop, audio frame forwarding, STT epoch management, and TTS streaming are all deleted.

##### [DELETE] [stt_provider_interface.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/domain/interfaces/stt_provider_interface.py)
Obsolete — widTTS no longer executes STT.

##### [DELETE] [tts_provider_interface.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/domain/interfaces/tts_provider_interface.py)
Obsolete — widTTS no longer executes TTS.

##### [DELETE] [deepgram_stt_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/deepgram/deepgram_stt_adapter.py)
Entire Deepgram STT streaming implementation including epoch queue, reconnect, parser.

##### [DELETE] [deepgram_tts_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/deepgram/deepgram_tts_adapter.py)
Entire Deepgram TTS streaming implementation.

##### [DELETE] [elevenlabs_stt_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/elevenlabs/elevenlabs_stt_adapter.py)
Entire ElevenLabs STT adapter.

##### [DELETE] [elevenlabs_tts_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/elevenlabs/elevenlabs_tts_adapter.py)
Entire ElevenLabs TTS adapter.

##### [DELETE] [provider_factory.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/provider_factory.py)
Replaced by `SpeechPluginFactory` which constructs LiveKit official plugins instead of widTTS adapters.

##### [DELETE] [synthesize_speech.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/application/use_cases/synthesize_speech.py)
Use case wrapping the old TTS adapter. Obsolete — LiveKit's pipeline drives TTS directly.

##### [DELETE] `backend/app/modules/voice/domain/interfaces/` (entire directory)
Both interfaces deleted; directory is empty.

##### [DELETE] `backend/app/modules/voice/infrastructure/providers/deepgram/` (entire directory)
##### [DELETE] `backend/app/modules/voice/infrastructure/providers/elevenlabs/` (entire directory)

---

### Phase 5 — Frontend Transport Integration

The frontend keeps its visual identity (Core UI, Orb, Transcript, ControlBar, 3D journey, glassmorphism, animations) but replaces the entire communication layer.

---

#### Frontend — New Files

##### [NEW] `frontend/src/hooks/useLiveKitRoom.js`
Replaces `useWebSocket.js`. Uses `livekit-client` (`Room`, `RoomEvent`, `LocalAudioTrack`, `RemoteAudioTrack`):
- `begin()`: POST `/realtime/token` → `Room.connect(serverUrl, token)` → publish mic as `LocalAudioTrack` → subscribe to agent's audio track → attach to `<audio>` element.
- Dispatches same `ConversationContext` actions (`SESSION_STARTED`, `APPEND_TRANSCRIPT_LINE`, `SET_PARTIAL_TRANSCRIPT`, `SET_ASSISTANT_HIGHLIGHT`, `SESSION_COMPLETED`, etc.) by listening to LiveKit `DataChannel` messages from the backend (for transcript text, session events).
- `end()`: `Room.disconnect()`, cleanup.
- Exposes `{ status, audioLevel, transcript, begin, end, restart, muted, setMuted }` — same shape as `useVoiceSession` expects.
- **No LiveKit React components** — pure imperative JS using `livekit-client`.

##### [NEW] `frontend/src/hooks/useRemoteAudioLevel.js`
Replaces the `audioVolumeTracker`-based polling. Uses `livekit-client`'s `RemoteTrack` API or an AnalyserNode on the subscribed audio track to derive the Orb's `audioLevel` reactivity.

---

#### Frontend — Modified Files

##### [MODIFY] [useVoiceSession.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/hooks/useVoiceSession.js)
- Replace `useWebSocket('active_bot')` with `useLiveKitRoom()`.
- Remove `audioVolumeTracker` polling. Use `useRemoteAudioLevel` instead.
- Same public API shape maintained for `HomePage`/`Core`.

##### [MODIFY] [ConversationContext.jsx](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/context/ConversationContext.jsx)
- Minimal changes: the reducer actions stay the same, the new hook dispatches the same action types. Minor adjustments if needed.

##### [MODIFY] [package.json](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/package.json)
- Add: `livekit-client`
- Remove: `@ricky0123/vad-web`, `onnxruntime-web`

---

#### Frontend — Deleted Files

##### [DELETE] [useWebSocket.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/hooks/useWebSocket.js)
Entire raw WebSocket hook. Replaced by `useLiveKitRoom.js`.

##### [DELETE] [useDeepgramAudio.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/hooks/useDeepgramAudio.js)
Mic capture via MediaRecorder, manual TTS playback, StreamingAudioPlayer management. All replaced by LiveKit `LocalAudioTrack`/`RemoteAudioTrack`.

##### [DELETE] [useVAD.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/hooks/useVAD.js)
Client-side Silero ONNX VAD. Replaced by server-side `livekit-plugins-silero`.

##### [DELETE] [useMicLevel.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/hooks/useMicLevel.js)
Manual AnalyserNode on mic stream. Replaced by `useRemoteAudioLevel`.

##### [DELETE] [websocketService.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/services/websocketService.js)
Raw WebSocket factory. Entire `services/` directory deleted.

##### [DELETE] `frontend/src/audio/` (entire directory)
- [AudioPipeline.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/audio/AudioPipeline.js) — RNNoise/HighPass/NoiseGate AudioWorklet chain
- [FlowController.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/audio/playback/FlowController.js) — Playback flow control
- [PlaybackQueueManager.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/audio/playback/PlaybackQueueManager.js) — TTS chunk queue
- [AudioMetrics.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/audio/metrics/AudioMetrics.js) — Audio quality metrics
- [AudioHealthMonitor.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/audio/health/AudioHealthMonitor.js) — Health monitoring
- [AudioStateMachine.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/audio/state/AudioStateMachine.js) — Audio state FSM
- [AudioConfig.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/audio/config/AudioConfig.js) — Audio configuration

##### [DELETE] `frontend/src/vad/` (entire directory)
- [VADStateMachine.ts](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/vad/VADStateMachine.ts)
- [AdaptiveThreshold.ts](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/vad/AdaptiveThreshold.ts)
- [SileroVAD.ts](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/vad/engines/SileroVAD.ts)
- [WebRTCVAD.ts](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/vad/engines/WebRTCVAD.ts)
- [vad.worker.ts](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/vad/worker/vad.worker.ts)
- [PreRollBuffer.ts](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/vad/buffers/PreRollBuffer.ts)
- [VADProvider.ts](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/vad/interfaces/VADProvider.ts)
- [vad-processor.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/vad/audio-worklet/vad-processor.js)

##### [DELETE] [audioUtils.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/utils/audioUtils.js)
`createMicStream`, `stopMicStream`, `playAudioBuffer`, `StreamingAudioPlayer`, `audioVolumeTracker`, `setTTSPlaying`. Entire file replaced by LiveKit's track management.

---

### Phase 6 — Admin UI Integration

##### [MODIFY] AdminJourney (frontend)
Add a "Realtime Connection" configuration pane in the existing glass-pane visual language. Fields: Server URL, API Key (masked), API Secret (masked), Token TTL, Audio Sample Rate, Test Connection button. No LiveKit terminology in any label.

---

### Phase 7 — Testing

#### Deleted Tests

##### [DELETE] [test_deepgram_stt_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/voice/test_deepgram_stt_adapter.py)
##### [DELETE] [test_deepgram_tts_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/voice/test_deepgram_tts_adapter.py)
##### [DELETE] [test_response_coordinator.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_response_coordinator.py) — TTS-flush path tests deleted; any remaining coordinator logic tests rewritten for bridge.

#### Kept Tests (must pass unmodified)

- [test_conversation_policy.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_conversation_policy.py) — unchanged business logic
- [test_turn_context.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_turn_context.py) — business-level tests (transport-adjacent tests removed)
- [test_runtime_state_manager.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/session/test_runtime_state_manager.py) — bot/turn tracking (audio-pipeline state tests removed)
- [test_context_manager.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_context_manager.py)
- [test_task_router.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_task_router.py)
- [test_validation_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/modules/conversation/test_validation_adapter.py)
- [test_event_bus.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/tests/shared/test_event_bus.py)

#### New Tests

##### [NEW] `backend/tests/modules/voice/test_speech_plugin_factory.py`
- Given a Deepgram config → asserts correct `deepgram.STT`/`deepgram.TTS` plugin with correct credentials/model/voice
- Given an ElevenLabs config → asserts correct `elevenlabs.STT`/`elevenlabs.TTS` plugin
- Unknown provider → raises `UnsupportedProviderError`

##### [NEW] `backend/tests/modules/voice/test_widtts_llm_bridge.py`
- Mocks `livekit.agents.llm.ChatContext`
- Policy-action short-circuit: STOP/REPEAT/CORRECTION/END
- Normal prompt-driven streaming response
- Asserts no import of `livekit-plugins-deepgram`/`elevenlabs` inside the bridge

##### [NEW] `backend/tests/integration/test_livekit_session.py`
- End-to-end: token mint → room join → `AgentSession.start()` → mocked STT emits transcript → `WidTTSLLMBridge.chat()` invoked → mocked TTS receives text → verify lifecycle cleanup

---

### Phase 8 — Zero Hardcoding Audit

Per SDD §9, run repo-wide greps after all changes:
- `grep -ri "livekit" backend/app/modules/*/domain backend/app/modules/*/application` → must return zero matches
- `grep -rE "deepgram|elevenlabs" backend/app` → only in `SpeechPluginFactory`, admin/config code, provider-name DB strings
- `grep -rE "16000|24000|48000" backend/app frontend/src` → only in config-loading code or documented constants
- `grep -rE "wss?://[^ ]*\.(deepgram|livekit|elevenlabs)" backend/app` → zero matches (all URLs from DB)
- Every hit resolved or justified in writing

---

### Phase 9 — Dependency Cleanup

##### Backend
- Remove: `deepgram-sdk`, `websockets` (if no other consumer)
- Verify: all remaining packages in `requirements.txt` have at least one active import

##### Frontend
- Remove: `@ricky0123/vad-web`, `onnxruntime-web`
- Remove from `public/` or `dist/`: `silero_vad_v5.onnx`, `vad.worklet.bundle.min.js`, `worklet.js`, `ort-wasm/` directory
- Remove: any AudioWorklet processor JS files served from `public/`
- Verify: all remaining packages in `package.json` have at least one active import

---

### Phase 10 — Documentation

#### [NEW] [migration_report.md](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/resources/docs/migration_report.md)
Updated architecture diagram, dependency/directory graphs, deleted component report, repository cleanup report, breaking changes doc.

#### [NEW] [developer_guide_livekit.md](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/resources/docs/developer_guide_livekit.md)
How to run a local LiveKit OSS server for development.

---

## Verification Plan

### Automated Tests
```bash
cd backend && python -m pytest tests/ -v
```
- `test_conversation_policy.py` passes unmodified
- `test_turn_context.py` passes (after removing transport-adjacent test cases)
- `test_runtime_state_manager.py` passes (after removing audio-pipeline state tests)
- `test_speech_plugin_factory.py` (new) passes
- `test_widtts_llm_bridge.py` (new) passes
- `test_livekit_session.py` (new) integration test passes

### Acceptance Criteria Verification (SDD §12)
```bash
# No LiveKit terminology in business layers
grep -ri "livekit" backend/app/modules/*/domain backend/app/modules/*/application
# → must return zero

# No custom STT/TTS streaming implementations
grep -rE "deepgram|elevenlabs" backend/app
# → only SpeechPluginFactory, admin/config, DB strings

# Repository size decreased
find . -name "*.py" -o -name "*.js" -o -name "*.ts" -o -name "*.jsx" | wc -l
# → must be less than pre-migration count
```

### Manual Verification
- End-to-end voice session: mic → LiveKit VAD/STT → `WidTTSLLMBridge` → LiveKit TTS → playback with barge-in
- Admin portal: configure Realtime Connection, test connection
- Frontend visuals unchanged (Orb, Transcript, ControlBar, 3D journey)
