# Real-Time Voice Assistant Platform

A multi-tenant, real-time AI voice assistant platform with an interactive 3D WebRTC client and a modular FastAPI backend.

- **Multi-Bot**: Create and configure independent bots with their own LLM, STT, TTS voice, system prompts, and custom greetings.
- **Provider Agnostic**: Deepgram (STT & TTS), ElevenLabs (STT & TTS), Fish Audio (TTS), and LiteLLM (OpenAI, Gemini, Anthropic, DeepSeek, etc.).
- **LiveKit WebRTC Core**: Low-latency bidirectional audio streaming with Silero VAD.
- **Zero-Config Database**: Serverless SQLite database with automated migrations and AES-256-GCM envelope encryption.

---

## 🚀 Quick Start (Choose Any Method)

### Method 1: Local Manual Setup (No Docker required)

#### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **LiveKit Server** (`brew install livekit` or download binary)

#### 1. Start LiveKit Server
```bash
livekit-server --config livekit.yaml
```

#### 2. Start Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

#### 3. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

* Open **`http://localhost:3000`** in your browser.

---

### Method 2: Docker Compose (Local Stack)

Runs LiveKit, Redis, Backend, and Frontend in containers.

```bash
docker compose up --build
```

* Frontend / Admin UI: **`http://localhost:3000`**
* Backend API: **`http://localhost:8000`**
* LiveKit WebRTC: **`ws://localhost:7880`**

---

### Method 3: Remote Tunneling with Ngrok

To expose your voice bot to mobile devices or remote users:

1. Add your ngrok token to `.env`:
   ```bash
   NGROK_AUTHTOKEN=your_token_here
   ```
2. Start the ngrok profile:
   ```bash
   docker compose --profile ngrok up --build
   ```
3. Check the public URL from the ngrok container logs:
   ```bash
   docker compose logs ngrok
   ```

---

## ⚙️ Environment Configuration

Create a `.env` file in the root directory (optional for local dev, all fields have working defaults):

```env
# ── Security & Encryption ──
MASTER_ENCRYPTION_KEY=   # Auto-generated if empty
APP_SECRET=dev-secret-change-in-production
ADMIN_API_KEY=admin-dev-key

# ── LiveKit Realtime Transport ──
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
LIVEKIT_TOKEN_TTL_SECONDS=3600

# ── Voice Engine Tuning ──
ROOM_INACTIVITY_TIMEOUT_SECONDS=60
AGENT_TOKEN_TTL_SECONDS=7200
```

---

## 🧪 Testing

Run backend unit and integration test suite:

```bash
cd backend
pytest tests/ -v
```

Build and test frontend production assets:

```bash
cd frontend
npm run build
```

---

## 📂 Project Structure

```
├── backend/
│   ├── app/
│   │   ├── entrypoints/http/        # Admin & public bot REST routes
│   │   ├── modules/                 # Bot, provider, session & voice domain
│   │   └── shared/                  # DB, security, envelope encryption, logging
│   ├── tests/                       # Complete pytest suite
│   ├── main.py                      # FastAPI app entrypoint
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/journey/      # 3D Radiant Sphere, Section Views
│   │   ├── hooks/                   # useLiveKitRoom, useVoiceSession
│   │   └── pages/                   # Admin Journey, BotLanding, HomePage
│   └── package.json
├── docker-compose.yml               # Multi-service container definitions
└── livekit.yaml                     # WebRTC port & IP configuration
```
