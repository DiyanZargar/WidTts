# widTTS — Voice Platform

A multi-tenant, real-time AI voice assistant platform built using Clean Architecture on the backend (FastAPI, PostgreSQL, LiveKit Agents, LiteLLM) and a modern 3D interactive visualizer on the frontend (React 18, Three.js / React Three Fiber, Vite 5, Tailwind CSS).

Each bot is independently configurable with its own LLM, TTS voice, STT model, system prompt, and languages. Deployed bots get unique shareable URLs (`/bot/{slug}`).

---

## 🏗️ Architectural Overview

* **Multi-Bot, Multi-Tenant**: Create multiple bots, each with independent LLM/TTS/STT config. Deploy each bot to a unique public URL. No shared state between bots.
* **Zero Hardcoding Policy**: All provider settings are managed dynamically via PostgreSQL with Envelope Encryption (AES-256-GCM). No secrets in application code.
* **LiveKit Infrastructure**: Realtime WebRTC audio runs server-side via official LiveKit plugins (Silero VAD, Deepgram, ElevenLabs). LiveKit is transport only — the app owns its architecture.
* **Single Seam LLM Bridge**: `WidTTSLLMBridge` implements `livekit.agents.llm.LLM`. It enforces conversation policies (STOP/REPEAT/CORRECTION/END) before delegating to the bot's configured LLM via LiteLLM.
* **LLM-Driven Personality**: Each bot generates its own greeting and goodbye based on its system prompt — no hardcoded text. The bot's identity (`"You are {bot_name}."`) is prepended to instructions.
* **3D Admin Journey**: Admin portal features a 7-stage interactive 3D scroll experience with glassmorphism UI, real-time connection verification, and per-bot configuration.

---

## 📂 Repository Structure

```
widTts/
├── backend/
│   ├── app/
│   │   ├── entrypoints/http/
│   │   │   ├── admin/               # Admin REST APIs (bots, providers, runtime)
│   │   │   ├── public_bot_routes.py # Public bot endpoints (/api/bot/{slug})
│   │   │   └── realtime_token_routes.py
│   │   ├── modules/
│   │   │   ├── bot/                 # Bot domain, repository, persistence
│   │   │   ├── conversation/        # Conversation policy, validation, prompts
│   │   │   ├── provider/            # LLM & Speech provider management
│   │   │   ├── session/             # Session tracking
│   │   │   └── voice/               # LiveKit session adapter, LLM bridge, speech plugin factory
│   │   └── shared/                  # Database, encryption, logging, config
│   ├── migrations/                  # SQL migration files
│   ├── tests/                       # pytest suite
│   ├── requirements.txt
│   └── main.py                      # FastAPI entrypoint
├── frontend/
│   ├── src/
│   │   ├── components/journey/
│   │   │   ├── sections/            # LLMSection, SpeechSection, BotIdentitySection, DeploySection, LiveSection
│   │   │   ├── CoreSphere.jsx       # 3D orb (admin + user portal)
│   │   │   └── AdminJourney.jsx     # Main orchestrator
│   │   ├── context/                 # ConversationContext state management
│   │   ├── hooks/                   # useLiveKitRoom, useVoiceSession
│   │   └── pages/
│   │       ├── BotLanding.jsx       # Public bot landing page (/bot/:slug)
│   │       └── HomePage.jsx         # Voice session UI (/bot/:slug/session)
│   └── package.json
├── docker-compose.yml               # PostgreSQL (5432) + LiveKit Server (7880)
├── livekit.yaml                     # LiveKit OSS configuration
└── README.md
```

---

## 🔑 LiveKit API Keys

### Local Development (Docker)

```bash
docker-compose up -d
```

Pre-configured in `livekit.yaml`:
* **Server URL**: `ws://localhost:7880`
* **API Key**: `devkey`
* **API Secret**: `secret`

### LiveKit Cloud (Production)

1. Sign up at [cloud.livekit.io](https://cloud.livekit.io)
2. Go to **Project Settings → Keys**
3. Copy WebSocket URL, API Key, API Secret into `backend/.env`

---

## ⚡ Quick Start

### 1. Start Services

```bash
docker-compose up -d
# PostgreSQL: localhost:5432 (db: widtts, user: widtts, pass: widtts_dev_password)
# LiveKit:    localhost:7880
```

### 2. Configure & Start Backend

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Verify: `http://localhost:8000/health`

### 3. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

App runs at `http://localhost:3000/`

---

## 🤖 Bot Workflow

### Admin Setup (Steps 1–4)

1. **LLM** — Add an LLM provider (OpenAI, Anthropic, OpenAI-Compatible) with API key
2. **Speech** — Add Deepgram or ElevenLabs speech provider with API key
3. **Bot** — Create a bot:
   - Name, description
   - LLM provider + model
   - STT provider + model + languages
   - TTS provider + model + languages
   - System prompt (defines personality, greeting style, conversation flow)
4. **Deploy** — Deploy the bot to get a shareable URL: `/bot/{slug}`

### User Experience

- Visit `/bot/{slug}` → landing page with bot name
- Click **Enter** → voice session at `/bot/{slug}/session`
- Bot greets the user in character (LLM-generated, not hardcoded)
- Bot says goodbye in character when the conversation ends

### Per-Bot Independence

Each bot maintains its own:
- LLM model + provider (api key, base URL)
- TTS model (Flux voices → Aura mapping for Deepgram, voice ID for ElevenLabs)
- STT model + languages
- System prompt + greeting behavior
- Deploy URL

---

## 🔒 Cascade Delete Protection

Deleting resources is protected to prevent breaking deployed bots:

| Resource | Protection |
|---|---|
| Deployed bot | Cannot delete — must undeploy first |
| LLM provider | Cannot delete if referenced by any bot |
| Speech provider | Cannot delete if referenced by any bot |

Backend returns `409 Conflict` with a descriptive message listing affected bots.

---

## 🗄️ Database Migrations

Migrations are stored in `backend/migrations/`. Run manually against PostgreSQL:

```bash
PGPASSWORD=widtts_dev_password psql -h localhost -U widtts -d widtts -f backend/migrations/001_bot_language_and_greeting.sql
```

### Migration 001: Bot Language & Greeting

Adds per-bot STT/TTS language configuration and greeting field:

```sql
ALTER TABLE bots ADD COLUMN IF NOT EXISTS stt_languages TEXT DEFAULT '["en"]';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS stt_primary_language TEXT DEFAULT 'en';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS tts_languages TEXT DEFAULT '["en"]';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS tts_primary_language TEXT DEFAULT 'en';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS greeting TEXT DEFAULT '';
```

---

## 🎨 Key Frontend Sections

| Section | Purpose |
|---|---|
| **LLM** | Configure LLM provider (API key, base URL, model list) |
| **Speech** | Configure speech provider (Deepgram / ElevenLabs API key) |
| **Bot** | Create/edit bots with independent config per section |
| **Deploy** | Deploy/undeploy bots, get shareable links |
| **Live** | Monitor active sessions and runtime health |

---

## 🧪 Testing

```bash
# Backend tests
cd backend
venv/bin/pytest tests/ -v

# Frontend production build
cd frontend
npm run build
```
