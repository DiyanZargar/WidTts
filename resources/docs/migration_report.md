# widTTS → LiveKit Migration Report

## Architecture Change

**Before:** Custom WebSocket transport with client-side audio pipeline (AudioPipeline, StreamingAudioPlayer, VAD, AudioWorklets) and server-side STT/TTS adapters (Deepgram, ElevenLabs) called directly via their SDKs.

**After:** LiveKit WebRTC transport with server-side voice pipeline. LiveKit Agents handles STT, TTS, VAD via official plugins. The only custom plugin is `WidTTSLLMBridge` which bridges LiveKit's LLM interface with widTTS's conversation policy and LLM infrastructure. Frontend uses `livekit-client` directly (no LiveKit React components).

## What Was Deleted (~15 modules)

### Backend
- `connection_manager.py` — Raw WebSocket connection manager
- `conversation_handler.py` — 417-line WebSocket endpoint handler
- `stt_provider_interface.py` — STT adapter interface
- `tts_provider_interface.py` — TTS adapter interface
- `deepgram_stt_adapter.py` — Deepgram STT streaming implementation
- `deepgram_tts_adapter.py` — Deepgram TTS streaming implementation
- `elevenlabs_stt_adapter.py` — ElevenLabs STT adapter
- `elevenlabs_tts_adapter.py` — ElevenLabs TTS adapter
- `provider_factory.py` — Old adapter factory
- `synthesize_speech.py` — TTS use case wrapper
- `voice/domain/interfaces/` — Empty interfaces directory

### Frontend
- `useWebSocket.js` — Raw WebSocket hook
- `useDeepgramAudio.js` — Mic capture + TTS playback
- `useVAD.js` — Client-side Silero ONNX VAD
- `useMicLevel.js` — Manual AnalyserNode on mic stream
- `websocketService.js` — WebSocket factory
- `audio/` directory — AudioPipeline, FlowController, PlaybackQueueManager, AudioMetrics, AudioHealthMonitor, AudioStateMachine, AudioConfig
- `vad/` directory — VADStateMachine, AdaptiveThreshold, SileroVAD, WebRTCVAD, PreRollBuffer, vad.worker.ts, vad-processor.js
- `HolographicOrb.jsx` — Dead visual component
- `audioUtils.js` — Stub audioVolumeTracker
- `silero_vad_v5.onnx` — 2.3MB stale ONNX model
- `ort-wasm/` — ONNX Runtime WebAssembly files

## What Was Added (~10 modules)

### Backend
- `widtts_llm_bridge.py` — Custom LiveKit LLM plugin (the only custom plugin)
- `speech_plugin_factory.py` — Constructs official LiveKit STT/TTS plugin instances
- `livekit_session_adapter.py` — Full session lifecycle management
- `realtime_token_routes.py` — `POST /realtime/token` endpoint
- `realtime_config_routes.py` — Admin CRUD + connection test
- `realtime_config_repository.py` — DB repository for `realtime_runtime_config`
- `0011_create_realtime_runtime_config.sql` — Database migration
- `structured_events.py` — SDD Extension observability event emitter

### Frontend
- `useLiveKitRoom.js` — Room connection, mic publish, remote audio, data channel, AnalyserNode-based audio levels
- `RealtimeSection.jsx` — Admin UI for realtime connection configuration

## Key Design Decisions

1. **Only custom plugin = WidTTSLLMBridge** — All STT/TTS/VAD is handled by official LiveKit plugins. The bridge implements `livekit.agents.llm.LLM` and routes through `ConversationPolicy` for intent classification before delegating to `DefaultConversationAdapter` for LLM streaming.

2. **Session API for frontend** — `useLiveKitRoom` handles token fetch, room connect, mic publish, remote audio subscribe, and data channel events. No `@livekit/components-react` — pure imperative `livekit-client`.

3. **Transport states removed from business logic** — `ConversationFSM` no longer has `WAITING_FOR_TTS`, `TTS_PLAYING`, `LISTENING`, `TRANSCRIBING`. `RuntimeStateManager` no longer tracks `ConnectionState`, `PlaybackState`, `STTState`, `TTSState`. LiveKit owns transport lifecycle.

4. **ResponseCoordinator decoupled from TTS** — `_tts_flush()` removed. The coordinator now emits `tts_text_ready` events; LiveKit's TTS plugin handles synthesis.

## Breaking Changes

- `/ws/{conversation_type}` WebSocket endpoint **deleted**. Replaced by `/realtime/token` + LiveKit room connection.
- All frontend audio pipeline code **deleted** (AudioPipeline, StreamingAudioPlayer, VAD, AudioWorklets, etc.).
- `@ricky0123/vad-web`, `onnxruntime-web`, `deepgram-sdk` packages **removed**.
- `websockets` package **removed** from requirements.
- New `realtime_runtime_config` table and admin panel required.
- `ResponseCoordinator.__init__` no longer takes `synthesize_speech` parameter.

---

## Multi-Bot Architecture (Phase 2)

### What Changed

The platform evolved from single-bot to multi-tenant with independent per-bot configuration and public deploy URLs.

### New Features

#### Public Bot Routes (`public_bot_routes.py`)
- `GET /api/bot/{slug}` — Public bot info (name, description)
- `POST /api/bot/{slug}/token` — Mint LiveKit token for a specific deployed bot
- Each bot gets its own LiveKit room, session, and voice pipeline

#### Deploy System
- Bots can be deployed to unique URLs: `/bot/{slug}`
- `DeploySection` — Admin UI for deploy/undeploy with GitHub-style name confirmation
- `BotLanding.jsx` — Public landing page at `/bot/:slug`
- Session page at `/bot/:slug/session` — full voice experience

#### Per-Bot Independent Config
Each bot maintains its own:
- LLM provider + model (via LiteLLM with `openai/` prefix for custom endpoints)
- TTS provider + model (Flux→Aura mapping for Deepgram, voice ID for ElevenLabs)
- STT provider + model + languages
- System prompt (placeholder in UI, not pre-filled)
- Bot identity: `"You are {bot_name}."` prepended to system prompt

#### LLM-Driven Greeting & Goodbye
- **Greeting**: `generate_reply(user_input="You are {bot_name}. A new user has just joined. Introduce yourself and greet them warmly in character.")`
- **Goodbye**: When user says goodbye, `END_CONVERSATION` policy lets the LLM generate its own farewell (no hardcoded `_END_ACK`)
- `_is_farewell()` detects farewell patterns in LLM response → schedules session end after 5s

#### Cascade Delete Protection
- Cannot delete a deployed bot (must undeploy first)
- Cannot delete LLM/Speech provider if referenced by any bot
- Backend returns 409 with descriptive message

#### TTS Preview Performance
- `POST /admin/api/speech-providers/prewarm` — Batch prewarm TTS models in backend cache
- All models prewarmed when TTS provider loads in Bot section
- 300ms debounce on model selection preview

### Database Migrations

```sql
-- 001_bot_language_and_greeting.sql
ALTER TABLE bots ADD COLUMN IF NOT EXISTS stt_languages TEXT DEFAULT '["en"]';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS stt_primary_language TEXT DEFAULT 'en';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS tts_languages TEXT DEFAULT '["en"]';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS tts_primary_language TEXT DEFAULT 'en';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS greeting TEXT DEFAULT '';
```

### UX Changes
- Delete modals: orange/red → emerald theme
- Save result: inline banner → fixed toast (bottom-right, auto-dismiss 5s)
- System prompt: pre-filled default → placeholder only
- Deploy section auto-refreshes after bot create/update
