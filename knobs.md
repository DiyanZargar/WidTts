# widTTS Voice Platform — Complete Knobs & Parameter Catalogue (`knobs.md`)

This document is the master reference for all operational knobs, thresholds, timing values, speech provider configurations, WebRTC room options, and noise-resistance parameters across the widTTS platform.

---

## 1. How to Make VAD & Interruption Act Like a Real Human

### The Problem with the Current Setup
In the default/current setup, the system behaves like a mechanical on/off switch:
- **Silero VAD `min_speech_duration` is 50ms**: Any brief breath, sneeze, mic bump, sniff, or key click (>50ms) triggers a `SpeechStarted` event.
- **Interruption `min_words` is 0**: As soon as *any* audio energy is detected for 200ms, the bot halts speech immediately without checking if any actual words were spoken.
- **Interruption `resume_false_interruption` is `False`**: If a loud sound pauses the bot, it permanently discards what it was saying instead of resuming.
- **`aec_warmup_duration` is 0.5s**: The bot's own voice from the speakers leaks into the microphone and causes it to interrupt itself.

---

### The 4-Layer Human-Like Interruption Architecture

```
User Audio Input (Microphone)
  │
  ├──► [Layer 1: Acoustic VAD Filter] (Silero VAD)
  │      ├─ Duration < 280ms (Sneezes, short coughs, throat clears, clicks) ──► DROPPED (No speech event)
  │      └─ Confidence < 0.68 (Background AC hum, fan noise, typing) ────────► DROPPED (No speech event)
  │
  ├──► [Layer 2: Linguistic Confirmation] (Deepgram STT + min_words)
  │      ├─ Non-verbal sound > 280ms (Medium cough, yawn, dog bark) ──► 0 Words Transcribed ──► NO INTERRUPTION
  │      └─ Actual words spoken ("Wait", "Stop", "Actually...") ───────► ≥ 1 Word Transcribed ──► AGENT INTERRUPTED
  │
  ├──► [Layer 3: Resilience & Recovery] (False Interruption Recovery)
  │      └─ Prolonged loud cough / shout (Audio energy > 550ms, but 0 words after 1.8s)
  │           ──► Agent pauses briefly ──► Detects 0 words ──► RESUMES SPEAKING where it left off!
  │
  └──► [Layer 4: Conversational Backchanneling] (backchannel_boundary)
         └─ Short affirmations ("uh-huh", "yeah", "mhm") within 0.8s - 1.2s ──► Agent IGNORES and continues talking
```

---

### How Specific Real-World Scenarios Are Handled:

| Real-World Scenario | Acoustic & Linguistic Reality | How the System Handles It |
| :--- | :--- | :--- |
| **Light cough / sniffle / throat clear** | Lasts 80–180ms. | Filtered out at **Layer 1** by `min_speech_duration = 0.28s`. The system ignores it completely. |
| **Sneeze** | Loud acoustic burst (200–350ms), but contains **no words**. | Filtered out at **Layer 2** by `min_words = 1` and `mode = "adaptive"`. Since STT hears no words, the agent continues talking. |
| **Direct speech ("Hey wait" / "No")** | Sustained vocal resonance > 280ms + STT transcribes "Hey" or "No" (1+ words). | Confirmed at **Layer 2**. The agent stops talking immediately and listens. |
| **Loud violent cough / Desk bang** | High energy lasting > 550ms triggers a brief pause. But STT produces 0 words within `false_interruption_timeout = 1.8s`. | Handled at **Layer 3** by `resume_false_interruption = True`. The agent automatically **resumes speaking** the rest of its sentence. |
| **Shouting words ("STOP TALKING!")** | Sustained loud acoustic energy + transcribed words. | Confirmed at **Layer 2**. The agent stops immediately and executes the `stop` policy. |
| **Backchannel ("yeah", "uh-huh", "mhm")** | Short utterance lasting 0.8s–1.2s followed by silence. | Handled at **Layer 4** by `backchannel_boundary = (0.8, 1.2)`. The agent keeps speaking without losing its train of thought. |
| **Speaker echo from device** | The agent's own voice echoes from speakers into the mic during the first few seconds of speech. | Ignored by `aec_warmup_duration = 2.5s` while hardware/browser echo cancellation adapts. |

---

## 2. Backend Support Status Legend

Every parameter in the tables below includes a **Backend Status Flag**:
- `✅ WIRED IN BACKEND`: Currently explicitly passed to LiveKit / plugin constructors in our backend logic.
- `⚡ SUPPORTED (READY TO WIRE)`: Natively supported by LiveKit Agent/Plugin constructor kwargs; directly accepted with zero custom code once passed.
- `ℹ️ APP SETTING / CONSTANT`: Used in application configuration, database, or policy routing.
- `🌐 FRONTEND WEBRTC`: Managed in client-side React / WebRTC connection.

---

## 3. Voice Activity Detection (Silero VAD)

Instantiated in [livekit_session_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/external/livekit_session_adapter.py#L58-L62) via `silero.VAD.load(...)`.

| Parameter | Type | Current in Code | LiveKit Default | Recommended | Backend Status | Plain-English Description & Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `min_speech_duration` | `float` (sec) | `0.05` (50ms) | `0.05` | **`0.28`** (280ms) | `✅ WIRED IN BACKEND` | **What it does:** The minimum continuous duration of sound before the system considers it speech.<br>• **Too low (50ms):** Tiny noises like keyboard taps, sniffles, and throat clears immediately trigger speech events.<br>• **Too high (>500ms):** The user has to talk for half a second before the bot even notices.<br>• **Why 0.28s:** Perfectly filters out sharp noises (<200ms) while capturing real words immediately. |
| `activation_threshold` | `float` (0–1) | `0.45` | `0.50` | **`0.68`** | `✅ WIRED IN BACKEND` | **What it does:** How confident (from 0% to 100%) the VAD neural network must be that incoming audio is a human voice.<br>• **Too low (<0.50):** Background fans, PC hums, and chair squeaks get flagged as human speech.<br>• **Too high (>0.85):** Quiet speakers or soft-spoken words might be ignored.<br>• **Why 0.68:** Demands clear human vocal harmonics, completely ignoring ambient room noise. |
| `deactivation_threshold` | `float` (0–1) | *(not set)* | `0.35` | **`0.48`** | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** The confidence floor below which speech is considered officially ended.<br>• **Why it matters:** Creates a buffer (hysteresis) with `activation_threshold`. Without this gap, natural volume dips between syllables cause the bot to rapidly toggle speech on and off. |
| `min_silence_duration` | `float` (sec) | `0.55` | `0.55` | **`0.65`** | `✅ WIRED IN BACKEND` | **What it does:** How long the user must remain silent before VAD decides they have finished an utterance.<br>• **Too low (<0.4s):** Cuts the user off every time they pause for a breath mid-sentence.<br>• **Too high (>1.2s):** The bot feels sluggish and takes too long to realize the user stopped talking.<br>• **Why 0.65s:** Gives natural breathing room while keeping conversations responsive. |
| `prefix_padding_duration` | `float` (sec) | *(not set)* | `0.50` | **`0.40`** | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Keeps a small audio buffer *before* the speech detection trigger.<br>• **Why it matters:** VAD takes ~50–100ms to confirm speech. Without prefix padding, the first syllable ("Hey", "So", "Well") gets clipped before reaching STT. |
| `max_buffered_speech` | `float` (sec) | *(not set)* | `60.0` | `60.0` | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Safety ceiling for buffered audio before forcing a frame flush to prevent memory leaks during non-stop noise. |
| `sample_rate` | `int` (Hz) | `16000` | `16000` | `16000` | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Audio sample rate passed into the Silero model. 16kHz is the native standard for optimal speech recognition accuracy. |
| `force_cpu` | `bool` | `True` | `True` | `True` | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Runs the ONNX VAD model on the CPU. CPU inference takes under 1ms and avoids GPU memory contention with LLM/TTS services. |

---

## 4. Turn-Taking & Interruption (Barge-In)

Configured in [livekit_session_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/external/livekit_session_adapter.py#L109-L116) via `AgentSession(turn_handling={"interruption": ...})`.

| Parameter | Type | Current in Code | LiveKit Default | Recommended | Backend Status | Plain-English Description & Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `enabled` | `bool` | `True` | `True` | `True` | `✅ WIRED IN BACKEND` | **What it does:** Master switch for barge-in capability. Allows the user to interrupt the bot while it is speaking. |
| `mode` | `Literal['adaptive', 'vad']` | `'vad'` (implied) | `'adaptive'` | **`'adaptive'`** | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Determines the intelligence used to detect interruptions.<br>• **`'vad'`:** Halts the bot purely on raw audio volume without knowing what was said.<br>• **`'adaptive'`:** Combines VAD + real-time STT word streams + acoustic energy. Required for true human-like conversation. |
| `min_duration` | `float` (sec) | `0.2` (200ms) | `0.5` | **`0.55`** | `✅ WIRED IN BACKEND` | **What it does:** How long the user must continuously speak before the bot interrupts itself.<br>• **Too low (0.2s):** A single cough or sneeze immediately halts the bot mid-sentence.<br>• **Why 0.55s:** Ensures only sustained vocal intention interrupts the bot. |
| `min_words` | `int` | `0` | `0` | **`1`** | `✅ WIRED IN BACKEND` | **What it does:** How many recognized English words STT must transcribe before cutting off the bot.<br>• **At 0 (current):** Any non-verbal noise (cough, sneeze, dog bark) interrupts the bot.<br>• **At 1 (recommended):** Sneezes and coughs produce 0 words and are **never** treated as interruptions. |
| `resume_false_interruption` | `bool` | `False` | `True` | **`True`** | `✅ WIRED IN BACKEND` | **What it does:** If a loud noise briefly pauses the bot but no words follow within the timeout window, the bot automatically **resumes speaking the interrupted sentence** instead of giving up. |
| `false_interruption_timeout` | `float` (sec) | *(not set)* | `2.0` | **`1.8`** | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Time window (in seconds) to wait for STT words after an acoustic trigger before deciding it was a false alarm and resuming playback. |
| `backchannel_boundary` | `tuple[float, float]` | `None` | `(1.0, 1.0)` | **`(0.8, 1.2)`** | `✅ WIRED IN BACKEND` | **What it does:** Window (min, max in seconds) for short affirmations like "uh-huh", "yeah", "ok". If the user makes a brief sound in this window and stops, the bot ignores it and keeps speaking. |
| `discard_audio_if_uninterruptible` | `bool` | `False` | `True` | **`True`** | `✅ WIRED IN BACKEND` | **What it does:** When the bot is speaking an uninterruptible line (e.g. farewell message), discards incoming microphone audio so it doesn't queue up an accidental delayed response. |

---

## 5. Endpointing (End-of-Turn Timing)

Configured in [livekit_session_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/external/livekit_session_adapter.py#L105-L108) via `AgentSession(turn_handling={"endpointing": ...})`.

| Parameter | Type | Current in Code | LiveKit Default | Recommended | Backend Status | Plain-English Description & Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `mode` | `Literal['fixed', 'dynamic']` | `'fixed'` (implied) | `'fixed'` | **`'dynamic'`** | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** How the system calculates when the user has finished speaking.<br>• **`'fixed'`:** Uses a rigid, static countdown timer.<br>• **`'dynamic'`:** Analyzes sentence structure and punctuation (shorter pause after a period, longer pause after a comma or question). |
| `min_delay` | `float` (sec) | `0.8` | `0.5` | **`0.55`** | `✅ WIRED IN BACKEND` | **What it does:** Minimum response delay after the user stops speaking. Lower values make the bot respond snappily when a complete sentence is detected. |
| `max_delay` | `float` (sec) | `3.0` | `3.0` | **`2.60`** | `✅ WIRED IN BACKEND` | **What it does:** Maximum time the bot will wait when the user is hesitating mid-sentence ("um... let me think...") before concluding they are done. |
| `alpha` | `float` (0–1) | *(not set)* | `0.9` | **`0.88`** | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Smoothing factor for dynamic endpointing calculation to prevent erratic timing shifts. |

---

## 6. Preemptive Generation & Turn Limits

Configured in `AgentSession(turn_handling={"preemptive_generation": ..., "user_turn_limit": ...})`.

| Parameter | Type | Current in Code | LiveKit Default | Recommended | Backend Status | Plain-English Description & Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `preemptive_generation.enabled` | `bool` | *(not set)* | `True` | `True` | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Starts speculative LLM generation while the user is finishing their sentence. Reduces response latency by ~200–400ms. |
| `preemptive_generation.preemptive_tts` | `bool` | *(not set)* | `False` | `False` | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Synthesizes audio on speculative tokens before the turn is confirmed. Kept `False` to prevent unnecessary TTS billing on aborted turns. |
| `preemptive_generation.max_speech_duration` | `float` (sec) | *(not set)* | `10.0` | `10.0` | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Maximum speech duration allowed for speculative token generation before resetting. |
| `preemptive_generation.max_retries` | `int` | *(not set)* | `3` | `3` | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Number of retries if speculative generation fails. |
| `user_turn_limit.max_words` | `Optional[int]` | `None` | `None` | `None` (or `150`) | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Caps continuous user speech at N words without pause to prevent prompt buffer exhaustion. |
| `user_turn_limit.max_duration` | `Optional[float]` | `None` | `None` | `None` (or `30.0`) | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Caps continuous user speech at N seconds without pause. |

---

## 7. AgentSession Core Runtime, Delays & Lifecycle

Configured in `AgentSession(...)` and [livekit_session_adapter.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/external/livekit_session_adapter.py#L97-L215).

| Parameter | Type | Current in Code | LiveKit Default | Recommended | Backend Status | Plain-English Description & Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `aec_warmup_duration` | `float` (sec) | `0.5` | `3.0` | **`2.5`** | `✅ WIRED IN BACKEND` | **What it does:** The grace period right after the agent starts speaking during which interruptions are ignored.<br>• **Too low (0.5s):** The bot's own voice comes out of the laptop speakers, enters the microphone, and the bot interrupts itself.<br>• **Why 2.5s:** Gives hardware/browser Acoustic Echo Cancellation enough time to adapt and cancel speaker echo. |
| `user_away_timeout` | `float` (sec) | `60.0` | `15.0` | `60.0` | `✅ WIRED IN BACKEND` | **What it does:** Mutual silence timeout (in seconds). If neither user nor bot speaks for 60 seconds, the user is marked "away" and the farewell teardown sequence triggers. |
| `transcription_timeout` | `Optional[float]` | `None` | `None` | **`3.0`** | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** If VAD detects speech but STT produces no words within N seconds, fires an event allowing the bot to politely say: "Sorry, I didn't catch that." |
| `session_close_transcript_timeout` | `float` (sec) | *(not set)* | `2.0` | `2.0` | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** How long the agent waits for trailing STT tokens when closing a session. |
| `min_consecutive_speech_delay` | `float` (sec) | *(not set)* | `0.0` | `0.0` | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Enforces a minimum pause between back-to-back agent speech turns. |
| `max_tool_steps` | `int` | *(not set)* | `3` | `3` | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Maximum consecutive tool calls allowed per single conversational turn. |
| `use_tts_aligned_transcript` | `bool` | *(not set)* | `False` | **`True`** | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Syncs UI subtitle / transcript word highlighting to the exact audio playback timestamp rather than text arrival time. |
| `tts_text_transforms` | `Sequence[str]` | *(not set)* | `None` | **`["filter_markdown", "filter_emoji"]`** | `⚡ SUPPORTED (READY TO WIRE)` | **What it does:** Automatically strips markdown formatting (`**bold**`, `# header`, `*bullet*`) and emojis from LLM text before passing to TTS so the voice doesn't read out symbols. |
| `greeting_stabilization_delay` | `float` (sec) | `0.5` | N/A | `0.5` | `ℹ️ APP SETTING / CONSTANT` | **What it does:** Sleep pause before sending the initial greeting. Prevents clipping the first word while the WebRTC audio channel connects. |
| `farewell_drain_delay` | `float` (sec) | `4.0` | N/A | `4.0` | `ℹ️ APP SETTING / CONSTANT` | **What it does:** Sleep pause to allow farewell TTS audio to finish playing on the user's speakers before disconnecting the room. |
| `farewell_publish_delay` | `float` (sec) | `0.5` | N/A | `0.5` | `ℹ️ APP SETTING / CONSTANT` | **What it does:** Brief pause after publishing the `session_end` data packet before tearing down WebRTC resources. |

---

## 8. Speech-to-Text (STT) Providers

### Deepgram STT — `livekit.plugins.deepgram.STT(...)`
Configured in [deepgram_provider.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/deepgram_provider.py#L44-L52).

| Parameter | Type | Current in Code | Deepgram Default | Recommended | Backend Status | Plain-English Description & Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `model` | `str` | `"nova-3"` | `"nova-3"` | `"nova-3"` | `✅ WIRED IN BACKEND` | Deepgram ASR model identifier. Nova-3 offers the fastest transcription and lowest word error rate. |
| `language` | `str` | `"en-US"` | `"en-US"` | Dynamic | `✅ WIRED IN BACKEND` | Primary speech recognition language code. |
| `interim_results` | `bool` | `True` | `True` | `True` | `✅ WIRED IN BACKEND` | **Critical:** Streams non-final partial words in real-time so the system can detect word-based interruptions instantly. |
| `punctuate` | `bool` | `True` | `True` | `True` | `✅ WIRED IN BACKEND` | Automatically inserts commas and periods. Required for dynamic endpointing to recognize sentence boundaries. |
| `smart_format` | `bool` | `True` | `False` | `True` | `✅ WIRED IN BACKEND` | Converts numbers, dates, currency into readable format ("$50" instead of "fifty dollars"). |
| `endpointing_ms` | `int` (ms) | `400` | `25` | **`350`** | `✅ WIRED IN BACKEND` | Deepgram-side silence duration before finalizing an utterance. 350ms prevents splitting one sentence into multiple turns. |
| `filler_words` | `bool` | *(not set)* | `True` | `True` | `⚡ SUPPORTED (READY TO WIRE)` | Transcribes "um", "uh" so the system knows the user is hesitating mid-sentence and doesn't cut them off. |
| `no_delay` | `bool` | *(not set)* | `True` | `True` | `⚡ SUPPORTED (READY TO WIRE)` | Emits interim words immediately without waiting for formatting buffers. |
| `vad_events` | `bool` | *(not set)* | `True` | `True` | `⚡ SUPPORTED (READY TO WIRE)` | Enables Deepgram-side VAD events over WebSocket. |
| `sample_rate` | `int` (Hz) | *(not set)* | `16000` | `16000` | `⚡ SUPPORTED (READY TO WIRE)` | Input audio sample rate in Hz. |
| `profanity_filter` | `bool` | *(not set)* | `False` | `False` | `⚡ SUPPORTED (READY TO WIRE)` | Masks offensive language with asterisks. |
| `redact` | `str | list[str]` | *(not set)* | `None` | `None` | `⚡ SUPPORTED (READY TO WIRE)` | Redacts sensitive data ("pci", "ssn", "numbers") for HIPAA/PCI compliance. |

### ElevenLabs STT — `livekit.plugins.elevenlabs.STT(...)`
Configured in [elevenlabs_provider.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/elevenlabs_provider.py#L25-L31).

| Parameter | Type | Current in Code | Default | Recommended | Backend Status | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `model_id` | `str` | `"scribe_v1"` | `"scribe_v1"` | `"scribe_v1"` | `✅ WIRED IN BACKEND` | ElevenLabs Scribe speech-to-text model. |
| `language_code` | `str` | `""` | `""` | Dynamic | `✅ WIRED IN BACKEND` | Target language code override. |

---

## 9. Text-to-Speech (TTS) Providers

### ElevenLabs TTS — `livekit.plugins.elevenlabs.TTS(...)` & `VoiceSettings`
Configured in [elevenlabs_provider.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/elevenlabs_provider.py#L33-L54).

| Parameter | Type | Current in Code | ElevenLabs Default | Recommended | Backend Status | Plain-English Description & Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `model` | `str` | `"eleven_turbo_v2_5"` | `"eleven_turbo_v2_5"` | `"eleven_turbo_v2_5"` | `✅ WIRED IN BACKEND` | Low-latency streaming TTS model optimized for real-time conversation. |
| `voice_id` | `str` | `"EXAVITQu4vr4xnSDxMaL"` | `"hpp4J3VqNfWAUOO0d1Us"` | `"EXAVITQu4vr4xnSDxMaL"` | `✅ WIRED IN BACKEND` | Voice ID fallback (Sarah, universally available across free and paid tiers). |
| `auto_mode` | `bool` | *(not set)* | `True` | `True` | `⚡ SUPPORTED (READY TO WIRE)` | Synthesizes sentence-by-sentence for lowest time-to-first-audio. |
| `apply_text_normalization` | `Literal['auto', 'off', 'on']` | *(not set)* | `'auto'` | `'auto'` | `⚡ SUPPORTED (READY TO WIRE)` | Spells out acronyms, numbers, and symbols naturally. |
| `inactivity_timeout` | `int` (sec) | *(not set)* | `180` | `180` | `⚡ SUPPORTED (READY TO WIRE)` | Keeps WebSocket connection alive to avoid reconnection latency. |
| `stability` | `float` (0–1) | *(not set)* | `0.50` | **`0.55`** | `⚡ SUPPORTED (READY TO WIRE)` | **Voice stability:** Higher = consistent and reliable tone; lower = expressive but prone to artifacts. |
| `similarity_boost` | `float` (0–1) | *(not set)* | `0.75` | **`0.80`** | `⚡ SUPPORTED (READY TO WIRE)` | How closely the generated voice matches the original voice sample. |
| `style` | `float` (0–1) | *(not set)* | `0.0` | `0.0` | `⚡ SUPPORTED (READY TO WIRE)` | Style exaggeration. Kept at 0.0 for lowest latency and natural pacing. |
| `speed` | `float` (0.5–2.0) | *(not set)* | `1.0` | `1.0` | `⚡ SUPPORTED (READY TO WIRE)` | Voice playback rate multiplier (1.0 = standard speed). |
| `use_speaker_boost` | `bool` | *(not set)* | `True` | `True` | `⚡ SUPPORTED (READY TO WIRE)` | Enhances voice clarity and presence. |

### Deepgram Aura TTS — `livekit.plugins.deepgram.TTS(...)`
Configured in [deepgram_provider.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/deepgram_provider.py#L58-L81).

| Parameter | Type | Current in Code | Default | Recommended | Backend Status | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `model` | `str` | `"aura-asteria-en"` | `"aura-2-andromeda-en"` | `"aura-asteria-en"` | `✅ WIRED IN BACKEND` | Deepgram Aura voice model identifier. |
| `sample_rate` | `int` (Hz) | *(not set)* | `24000` | `24000` | `⚡ SUPPORTED (READY TO WIRE)` | Audio output sample rate (24kHz high-fidelity speech). |
| `encoding` | `str` | *(not set)* | `"linear16"` | `"linear16"` | `⚡ SUPPORTED (READY TO WIRE)` | Uncompressed 16-bit linear PCM audio format. |

### Fish Audio TTS — `FishAudioTTS`
Configured in [fish_audio_provider.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/providers/fish_audio_provider.py#L37-L246).

| Parameter | Type | Current in Code | Default | Recommended | Backend Status | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `model` | `str` | `"s2.1-pro"` | `"s2.1-pro"` | `"s2.1-pro"` | `✅ WIRED IN BACKEND` | Fish Audio speech model. |
| `sample_rate` | `int` (Hz) | `24000` | `24000` | `24000` | `✅ WIRED IN BACKEND` | Output audio sample rate in Hz. |
| `num_channels` | `int` | `1` | `1` | `1` | `✅ WIRED IN BACKEND` | Mono audio channel. |
| `connect_timeout` | `int` (sec) | `15` | `15` | `15` | `✅ WIRED IN BACKEND` | Socket connection timeout for Fish Audio REST endpoint. |
| `total_timeout` | `int` (sec) | `30` | `30` | `30` | `✅ WIRED IN BACKEND` | Total request timeout for audio synthesis. |

---

## 10. LiveKit Room & WebRTC Room Configuration

Configured across `livekit.agents.voice.room_io.RoomOptions`, `AudioOutputOptions`, `AudioInputOptions`, `TextOutputOptions`, and [settings.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/shared/config/settings.py).

| Parameter | Type | Current Value | LiveKit Default | Recommended | Backend Status | Plain-English Description & Impact |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `text_output.sync_transcription` | `bool` | `False` | `True` | `False` | `✅ WIRED IN BACKEND` | **What it does:** If `False`, text subtitles appear immediately in the UI without waiting for TTS audio sync, making the interface feel instant. |
| `text_output.transcription_speed_factor` | `float` | *(not set)* | `1.0` | `1.0` | `⚡ SUPPORTED (READY TO WIRE)` | Speed multiplier when synchronizing text output. |
| `text_output.json_format` | `bool` | *(not set)* | `False` | `False` | `⚡ SUPPORTED (READY TO WIRE)` | Formats text output events as raw JSON payloads instead of plain text. |
| `audio_output.sample_rate` | `int` (Hz) | `24000` | `24000` | `24000` | `⚡ SUPPORTED (READY TO WIRE)` | WebRTC audio track publishing sample rate (24kHz is optimal for Opus speech). |
| `audio_output.num_channels` | `int` | `1` | `1` | `1` | `⚡ SUPPORTED (READY TO WIRE)` | Audio channel count (1 = mono). |
| `audio_output.track_name` | `str` | *(not set)* | `"agent_audio"` | `"agent_audio"` | `⚡ SUPPORTED (READY TO WIRE)` | Published WebRTC audio track identifier. |
| `audio_input.frame_size_ms` | `int` | *(not set)* | `10` | `10` | `⚡ SUPPORTED (READY TO WIRE)` | Audio frame slice chunk duration in milliseconds for ingest processing. |
| `audio_input.auto_gain_control` | `bool` | *(not set)* | `True` | `True` | `⚡ SUPPORTED (READY TO WIRE)` | Ingest automatic gain control on the server side. |
| `audio_input.pre_connect_audio` | `bool` | *(not set)* | `False` | `True` | `⚡ SUPPORTED (READY TO WIRE)` | Buffers audio during WebRTC connection handshake so early user words are not lost. |
| `audio_input.pre_connect_audio_timeout` | `float` (sec) | *(not set)* | `3.0` | `3.0` | `⚡ SUPPORTED (READY TO WIRE)` | Timeout window for early pre-connect audio buffer. |
| `close_on_disconnect` | `bool` | `True` | `True` | `True` | `⚡ SUPPORTED (READY TO WIRE)` | Automatically shuts down the backend agent session when the user leaves the room. |
| `delete_room_on_close` | `bool` | `False` | `False` | `False` | `⚡ SUPPORTED (READY TO WIRE)` | Deletes the room record on the LiveKit server upon session close. |
| `livekit_token_ttl_seconds` | `int` (sec) | `3600` (1 hr) | `3600` | `3600` | `ℹ️ APP SETTING / CONSTANT` | Expiration lifetime for user room connection JWT tokens. |
| `agent_token_ttl_seconds` | `int` (sec) | `7200` (2 hr) | `7200` | `7200` | `ℹ️ APP SETTING / CONSTANT` | Expiration lifetime for background agent worker room JWT tokens. |
| `room_inactivity_timeout_seconds` | `float` (sec) | `60.0` | `60.0` | `60.0` | `ℹ️ APP SETTING / CONSTANT` | Idle duration before the room is closed due to inactivity. |

---

## 11. LLM Bridge & Deterministic Conversation Policy

Configured in [llm_bridge.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/voice/infrastructure/external/llm_bridge.py#L105-L180) and [conversation_policy.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/modules/conversation/domain/policy/conversation_policy.py#L33-L38).

| Parameter / Constant | Type | Current Value | Where It Lives | Backend Status | Plain-English Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `default_model` | `str` | `"gpt-4o-mini"` | `llm_bridge.py:105` | `ℹ️ APP SETTING / CONSTANT` | Default fallback LLM model identifier. |
| `temperature` | `float` | `0.7` | LiteLLM default | `ℹ️ APP SETTING / CONSTANT` | LLM randomness (0.0 = deterministic, 1.0 = creative). |
| `top_p` | `float` | `1.0` | LiteLLM default | `ℹ️ APP SETTING / CONSTANT` | Nucleus sampling probability threshold. |
| `max_tokens` | `int` | `1024` | LiteLLM default | `ℹ️ APP SETTING / CONSTANT` | Maximum response token ceiling. |
| `stream` | `bool` | `True` | `llm_bridge.py:150` | `✅ WIRED IN BACKEND` | Streams LLM response tokens directly into the TTS engine for instant voice generation. |
| `error_fallback_text` | `str` | `"I'm sorry, I had trouble generating a response. Could you try again?"` | `llm_bridge.py:169` | `ℹ️ APP SETTING / CONSTANT` | Spoken when LLM generation fails unexpectedly. |
| `stop_ack_text` | `str` | `"Alright, I'll pause here. Just say 'continue' when you're ready."` | `llm_bridge.py:174` | `ℹ️ APP SETTING / CONSTANT` | Instant zero-LLM spoken reply when the user commands "stop". |
| `end_ack_text` | `str` | `"Thanks for chatting! Goodbye."` | `llm_bridge.py:175` | `ℹ️ APP SETTING / CONSTANT` | Instant zero-LLM spoken reply when the user says "goodbye" or "end conversation". |
| `repeat_fallback_text` | `str` | `"I don't have a previous response to repeat."` | `llm_bridge.py:176` | `ℹ️ APP SETTING / CONSTANT` | Spoken if the user commands "repeat" but no prior turn exists. |
| `farewell_marker` | `str` | `"[END_SESSION]"` | `llm_bridge.py:179` | `ℹ️ APP SETTING / CONSTANT` | Marker appended to LLM prompt responses to signal natural conversational conclusion. |
| `default_farewell_speech` | `str` | `"It was nice talking with you. Goodbye!"` | `livekit_session_adapter.py:132` | `ℹ️ APP SETTING / CONSTANT` | Farewell message spoken when the session times out due to inactivity. |
| `default_bot_name` | `str` | `"Assistant"` | `livekit_session_adapter.py:161` | `ℹ️ APP SETTING / CONSTANT` | Fallback assistant name when none is configured. |
| `stop_commands` | `Set[str]` | `{"stop", "stop talking", "be quiet", "shut up", "pause", "quiet"}` | `conversation_policy.py:33` | `ℹ️ APP SETTING / CONSTANT` | Instant keywords that immediately pause the bot without calling the LLM. |
| `end_commands` | `Set[str]` | `{"end", "end conversation", "start over", "reset", "quit", "i'm done", "goodbye"}` | `conversation_policy.py:34` | `ℹ️ APP SETTING / CONSTANT` | Instant keywords that reset and end the session without calling the LLM. |
| `repeat_commands` | `Set[str]` | `{"repeat", "say that again", "what did you say", "pardon"}` | `conversation_policy.py:35` | `ℹ️ APP SETTING / CONSTANT` | Instant keywords that repeat the last bot response without calling the LLM. |
| `continue_commands` | `Set[str]` | `{"continue", "go on", "proceed", "keep going"}` | `conversation_policy.py:36` | `ℹ️ APP SETTING / CONSTANT` | Instant keywords that resume talking after a pause. |
| `forget_commands` | `Set[str]` | `{"forget that", "never mind", "disregard", "ignore that"}` | `conversation_policy.py:37` | `ℹ️ APP SETTING / CONSTANT` | Instant keywords that discard the last turn from memory. |

---

## 12. Frontend WebRTC Microphone Capture & Constraints

Configured in [useLiveKitRoom.js](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/frontend/src/hooks/useLiveKitRoom.js#L175-L180).

| Parameter | Type | Current Value | Recommended | Backend Status | Plain-English Description & Impact |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `echoCancellation` | `bool` | `true` | `true` | `🌐 FRONTEND WEBRTC` | Hardware/browser Acoustic Echo Cancellation (AEC). Prevents the bot's speaker audio from looping back into the microphone. |
| `noiseSuppression` | `bool` | `true` | `true` | `🌐 FRONTEND WEBRTC` | Browser-level background noise filter (suppresses air conditioners, PC fans, and typing). |
| `autoGainControl` | `bool` | `true` | `true` | `🌐 FRONTEND WEBRTC` | Automatically normalizes microphone volume so quiet and loud users sound balanced. |
| `sampleRate` | `int` (Hz) | `48000` | `48000` | `🌐 FRONTEND WEBRTC` | Browser microphone capture rate. |
| `channelCount` | `int` | `1` | `1` | `🌐 FRONTEND WEBRTC` | Mono microphone input. |

---

## 13. Outbound HTTP & Admin Network Timeouts

Configured in [speech_provider_routes.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/http/admin/speech_provider_routes.py) and [llm_provider_routes.py](file:///Users/rid/Developer/Extends/cmdXSec/Work/widTts/backend/app/entrypoints/http/admin/llm_provider_routes.py).

| Parameter | Type | Current Value | Where It Lives | Backend Status | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `health_check_timeout` | `float` (sec) | `3.0` | `speech_provider_routes.py:305` | `ℹ️ APP SETTING / CONSTANT` | Quick health check probe timeout for speech providers. |
| `provider_verify_timeout` | `float` (sec) | `8.0` | `speech_provider_routes.py:73, 97, 242` & `llm_provider_routes.py:134` | `ℹ️ APP SETTING / CONSTANT` | Verification timeout when testing user API keys. |
| `model_fetch_timeout` | `float` (sec) | `10.0` | `speech_provider_routes.py:150` | `ℹ️ APP SETTING / CONSTANT` | Timeout when fetching remote voice and model lists from providers. |
