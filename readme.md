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
│   │   └── shared/
│   │       ├── config/settings.py   # Centralized Pydantic Settings
│   │       ├── database/            # asyncpg pool, migrations, init
│   │       └── security/            # Envelope encryption, token service
│   ├── tests/                       # pytest suite (114 tests)
│   ├── app/shared/database/migrations_pg/  # SQL migration files (auto-applied at startup)
│   ├── Dockerfile                   # Multi-stage backend image (Python 3.11-slim)
│   ├── .dockerignore
│   ├── .env.example                 # Backend env template (local dev)
│   ├── requirements.txt
│   └── main.py                      # FastAPI entrypoint
├── frontend/
│   ├── src/
│   │   ├── components/journey/
│   │   │   ├── sections/            # LLMSection, SpeechSection, BotIdentitySection, DeploySection, LiveSection, RealtimeSection
│   │   │   ├── CoreSphere.jsx       # 3D orb (admin + user portal)
│   │   │   └── AdminJourney.jsx     # Main orchestrator
│   │   ├── context/                 # ConversationContext state management
│   │   ├── hooks/                   # useLiveKitRoom, useVoiceSession
│   │   └── pages/
│   │       ├── BotLanding.jsx       # Public bot landing page (/bot/:slug)
│   │       └── HomePage.jsx         # Voice session UI (/bot/:slug/session)
│   ├── Dockerfile                   # Multi-stage frontend image (Node 22 + Nginx Alpine)
│   ├── nginx.conf                   # SPA + API reverse proxy
│   ├── .dockerignore
│   ├── .env.example                 # Frontend env template
│   ├── package.json
│   └── vite.config.js               # Vite dev server + proxy config
├── docker-compose.yml               # 4-service stack (postgres, livekit, backend, frontend)
├── .env.example                     # Root env template (Docker deployment)
├── .gitignore
├── livekit.yaml                     # LiveKit OSS configuration
└── README.md
```

---

## 🔑 LiveKit API Keys

### Local Development

Pre-configured in `livekit.yaml`:
* **Server URL**: `ws://localhost:7880`
* **API Key**: `devkey`
* **API Secret**: `secret`

### LiveKit Cloud (Production)

1. Sign up at [cloud.livekit.io](https://cloud.livekit.io)
2. Go to **Project Settings → Keys**
3. Copy WebSocket URL, API Key, API Secret into `.env`

---

## ⚡ Local Development (Without Docker)

Run backend and frontend directly on your machine. Only PostgreSQL and LiveKit run in Docker.

### Prerequisites

* Python 3.11+
* Node.js 18+
* Docker & Docker Compose v2+

### 1. Start Infrastructure (PostgreSQL + LiveKit)

```bash
cd widTts
docker compose up -d postgres livekit
```

This starts:
- **PostgreSQL** on `localhost:5432` (db: `widtts`, user: `widtts`, pass: `widtts_dev_password`)
- **LiveKit Server** on `localhost:7880`

### 2. Configure & Start Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env

# Generate master encryption key (Base64-encoded 32-byte AES-256)
KEY=$(python3 -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())")
sed -i '' "s|MASTER_ENCRYPTION_KEY=.*|MASTER_ENCRYPTION_KEY=${KEY}|" .env

# Start backend (with hot-reload)
uvicorn main:app --reload --port 8000
```

The backend will:
- Connect to PostgreSQL at `localhost:5432`
- Run all database migrations automatically
- Seed a default realtime transport config pointing to `ws://localhost:7880`
- Bootstrap the encryption key

Verify:
```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

### 3. Start Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (with hot-reload + API proxy)
npm run dev
```

The Vite dev server runs on `http://localhost:3000` and automatically proxies API requests (`/health`, `/admin/api/`, `/realtime/`, `/api/bot/`) to the backend at `localhost:8000`.

### 4. Open the App

Open http://localhost:3000 in your browser.

---

## 🐳 Docker Deployment (Full Containerized Stack)

All four services (PostgreSQL, LiveKit, Backend, Frontend) run inside Docker containers.

### Prerequisites

- Docker Engine 24.0+
- Docker Compose v2+

### 1. Environment Setup & Key Generation

```bash
cd widTts

# Copy environment template
cp .env.example .env

# Generate a secure Base64 MASTER_ENCRYPTION_KEY into .env (Cross-Platform)
python3 -c "import os,base64; k=base64.b64encode(os.urandom(32)).decode(); open('.env','w').write(open('.env.example').read().replace('REPLACE_WITH_BASE64_32_BYTE_MASTER_KEY', k))"
```

Verify the key was set:
```bash
grep MASTER_ENCRYPTION_KEY .env
```

### 2. Build Images

Validate configuration first:
```bash
docker compose config
```

Build all images:
```bash
docker compose build
```

Build a specific service only:
```bash
docker compose build backend
docker compose build frontend
```

Clean rebuild (force fresh build without cache):
```bash
docker compose build --no-cache
```

### 3. Launch the Stack

Start entire stack in background (recommended):
```bash
docker compose up -d
```

Build and start in one command:
```bash
docker compose up -d --build
```

Start stack in foreground (view stdout in terminal):
```bash
docker compose up
```

Start specific services only (e.g. only infrastructure):
```bash
docker compose up -d postgres livekit
```

### 4. Verify Health

Check container status and health checks:
```bash
docker compose ps
```

All four containers should report `healthy` or `running`.

Verify endpoints:
```bash
curl -s http://localhost:8000/health   # Backend direct
curl -s http://localhost:3000/health   # Via Nginx proxy
curl -s http://localhost:7880          # LiveKit server
```

### 5. Open the App

Open http://localhost:3000 in your browser.

---

## 🔧 Environment Variables

All runtime configuration is driven by environment variables. The backend uses a centralized Pydantic `Settings` class (`backend/app/shared/config/settings.py`).

### Root `.env` (Docker Deployment)

| Variable | Purpose | Default / Source |
|---|---|---|
| `POSTGRES_USER` | Database username | `widtts` *(built-in dev default)* |
| `POSTGRES_PASSWORD` | Database password | `widtts_dev_password` *(built-in dev default)* |
| `POSTGRES_HOST` | Database hostname | `postgres` (Docker) / `localhost` (local) |
| `POSTGRES_PORT` | Database port | `5432` |
| `POSTGRES_DB` | Database name | `widtts` |
| `MASTER_ENCRYPTION_KEY` | Base64 32-byte AES-256 master key | **Generated by user** via `python3 -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"` |
| `APP_SECRET` | Application session secret | `dev-secret-change-in-production` |
| `LIVEKIT_URL` | Browser/public-facing LiveKit URL | `ws://localhost:7880` *(local Docker)* or Cloud URL (`cloud.livekit.io`) |
| `LIVEKIT_INTERNAL_URL` | Backend container→LiveKit URL | `ws://livekit:7880` *(Docker container network)* |
| `LIVEKIT_API_KEY` | LiveKit API key | `devkey` *(local Docker)* or Cloud Key (`cloud.livekit.io`) |
| `LIVEKIT_API_SECRET` | LiveKit API secret | `secret` *(local Docker)* or Cloud Secret (`cloud.livekit.io`) |
| `LIVEKIT_TOKEN_TTL_SECONDS` | LiveKit token expiry | `3600` |
| `LIVEKIT_AUDIO_SAMPLE_RATE` | Audio sample rate (Hz) | `16000` |
| `AGENT_TOKEN_TTL_SECONDS` | Agent JWT expiry | `7200` |
| `ROOM_INACTIVITY_TIMEOUT_SECONDS` | Idle session timeout | `30` |

### Backend `backend/.env` (Local Development)

Same variables, but:
- `POSTGRES_HOST=localhost` (not `postgres`)
- `LIVEKIT_INTERNAL_URL` is not needed (backend connects directly to `localhost:7880`)

### Frontend `frontend/.env`

| Variable | Purpose |
|---|---|
| `VITE_WS_BASE_URL` | WebSocket base URL (dev proxy only) |

> **Security**: No backend secrets (`MASTER_ENCRYPTION_KEY`, `APP_SECRET`, `LIVEKIT_API_SECRET`, `POSTGRES_PASSWORD`) are ever exposed to the frontend build or browser JavaScript.

### Dual LiveKit URL Design

The system uses two LiveKit URLs:

* **`LIVEKIT_URL`** — The browser-facing URL. Stored in the database `realtime_runtime_config.server_url` and returned in token API responses. The browser connects to LiveKit directly using this URL.
* **`LIVEKIT_INTERNAL_URL`** — The backend container-internal URL. Used by the agent session adapter when connecting to LiveKit from inside the Docker network. Falls back to `LIVEKIT_URL` if not set.

In Docker: browser uses `ws://localhost:7880`, backend agent uses `ws://livekit:7880`.
Locally: both use `ws://localhost:7880`.

---

## 📋 Docker Operations

### Checking Images, Containers & Status

```bash
# Check created Docker images
docker compose images

# Alternative
docker images | grep -E "widtts|postgres|livekit"

# Check container running status & health
docker compose ps

# Inspect container details
docker inspect widtts-backend
docker inspect widtts-frontend

# Inspect Docker network
docker network inspect widtts_widtts-network

# List volumes
docker volume ls | grep widtts
```

### Log Monitoring & Diagnostics

```bash
# Stream logs from all services
docker compose logs -f

# Stream logs from a specific service
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f postgres
docker compose logs -f livekit

# View last 50 lines of backend logs
docker compose logs --tail=50 backend
```

### Health & Endpoint Verification

```bash
# Check direct backend health
curl -s -i http://localhost:8000/health

# Check frontend Nginx proxied health
curl -s -i http://localhost:3000/health

# Check LiveKit server HTTP response
curl -s -i http://localhost:7880

# Check realtime token minting (browser address verification)
curl -s -X POST http://localhost:8000/realtime/token \
  -H "Content-Type: application/json" \
  -d '{"conversation_type":"active_bot"}'
```

### Database & Migration Management

```bash
# Inspect applied database migrations
docker compose exec postgres psql -U widtts -d widtts \
  -c "SELECT filename, applied_at FROM schema_migrations ORDER BY filename;"

# Inspect seeded transport config
docker compose exec postgres psql -U widtts -d widtts \
  -c "SELECT name, provider_type, server_url, is_active FROM realtime_runtime_config;"

# Enter interactive PostgreSQL CLI
docker compose exec -it postgres psql -U widtts -d widtts
```

### Executing Tests

```bash
# Run full backend pytest suite inside container
docker compose exec backend pytest tests/ -v

# Run a specific test file
docker compose exec backend pytest tests/test_session_launcher.py -v

# Run a specific test
docker compose exec backend pytest tests/test_settings.py::TestSettingsDefaults::test_default_livekit_url -v
```

### Container Shell Access (Debugging)

```bash
# Open terminal inside backend container
docker compose exec -it backend /bin/sh

# Open terminal inside frontend (Nginx) container
docker compose exec -it frontend /bin/sh

# Run a one-off Python command inside backend
docker compose exec backend python3 -c "from app.shared.config.settings import settings; print(settings.livekit_url)"

# Check backend environment variables
docker compose exec backend env | grep -E "POSTGRES|LIVEKIT|MASTER"
```

### Restarting & Cleanup

```bash
# Restart a single service
docker compose restart backend

# Restart all services
docker compose restart

# Stop the entire stack (preserves database data)
docker compose down

# Stop stack AND reset database (wipes database volume)
# ⚠️ Warning: This permanently deletes all stored bots, providers, sessions, and encryption keys
docker compose down -v
```

### Rebuilding After Code Changes

```bash
# Rebuild and restart a single service
docker compose build backend
docker compose up -d --force-recreate backend

# Rebuild and restart everything
docker compose build
docker compose up -d --force-recreate

# Full clean rebuild (no cache + recreate)
docker compose build --no-cache
docker compose down
docker compose up -d
```

---

## 🤖 Bot Workflow

### Admin Setup (Steps 1–4)

Open the Admin Portal at http://localhost:3000

1. **LLM** — Add an LLM provider (OpenAI, Anthropic, OpenAI-Compatible) with API key
2. **Speech** — Add Deepgram, ElevenLabs, or Fish Audio speech provider with API key
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
- LLM model + provider (API key, base URL)
- TTS model (Flux voices → Aura mapping for Deepgram, voice ID for ElevenLabs, custom voice profiles for Fish Audio)
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

Migrations are stored in `backend/app/shared/database/migrations_pg/` and run automatically at application startup. No manual migration step is needed.

The system uses a `schema_migrations` table to track which migrations have been applied. On each startup, only pending migrations are executed.

---

## 🎨 Key Frontend Sections

| Section | Purpose |
|---|---|
| **LLM** | Configure LLM provider (API key, base URL, model list) |
| **Speech** | Configure speech provider (Deepgram / ElevenLabs / Fish Audio) |
| **Bot** | Create/edit bots with independent config per section |
| **Deploy** | Deploy/undeploy bots, get shareable links |
| **Realtime** | Configure realtime transport (LiveKit URL, API keys) |
| **Live** | Monitor active sessions and runtime health |

---

## 🧪 Testing

```bash
# Backend tests (inside Docker container)
docker compose exec backend pytest tests/ -v

# Backend tests (local with venv)
cd backend
source venv/bin/activate
pytest tests/ -v

# Frontend production build (already runs during Docker build)
cd frontend
npm run build
```

---

## 🌐 Networking

```
Host Browser ──HTTP :3000──▶ FRONTEND (Nginx) ──HTTP──▶ BACKEND (FastAPI)
                               │                            │
                               │                            ├──▶ POSTGRES (postgres:5432)
                               │                            └──▶ LIVEKIT (ws://livekit:7880)
Host Browser ──WS :7880──────▶ LIVEKIT SERVER
```

| Path | Protocol | Description |
|---|---|---|
| Browser → Frontend | HTTP :3000 | Serves React SPA |
| Frontend → Backend | HTTP | Nginx reverse proxy (`http://backend:8000`) |
| Backend → PostgreSQL | TCP | Docker DNS (`postgres:5432`) |
| Backend → LiveKit | WebSocket | Docker DNS (`ws://livekit:7880`) |
| Browser → LiveKit | WebSocket | Host-mapped port (`ws://localhost:7880`) |

---

## 🔍 Troubleshooting

| Symptom | Diagnostic Command | What to Look For |
|---|---|---|
| Container restarting | `docker compose logs backend` | Startup traceback or missing env var |
| Database connection failed | `docker compose ps postgres` | Must be `healthy` |
| LiveKit unreachable from backend | `docker compose exec backend python3 -c "import httpx; print(httpx.get('http://livekit:7880').status_code)"` | Should return `200` |
| Browser can't connect to LiveKit | `docker compose ps livekit` | Verify port 7880 is mapped |
| Token endpoint returns 503 | `curl -s http://localhost:8000/realtime/token -X POST -H "Content-Type: application/json" -d '{}'` | No active bot configured |
| Frontend shows blank page | `docker compose logs frontend` | Check Nginx errors |
| Migration errors | `docker compose logs backend` | Check SQL syntax in migration files |
| Encryption key errors | `grep MASTER_ENCRYPTION_KEY .env` | Must be a valid Base64 string |
| Build failure | `docker compose build --no-cache backend 2>&1` | Check pip/npm network or compilation errors |
| Port conflict | `lsof -i :3000` / `lsof -i :8000` / `lsof -i :7880` | Kill conflicting process or change port mapping |
