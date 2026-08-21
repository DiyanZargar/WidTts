# Real-Time Voice Assistant Platform

A multi-tenant, real-time AI voice assistant platform with an interactive 3D WebRTC client and a modular FastAPI backend.

- **Multi-Bot**: Create and configure independent bots with their own LLM, STT, TTS voice, system prompts, and custom greetings.
- **Provider Agnostic**: Deepgram (STT & TTS), ElevenLabs (STT & TTS), Fish Audio (TTS), and LiteLLM (OpenAI, Gemini, Anthropic, DeepSeek, etc.).
- **LiveKit WebRTC Core**: Low-latency bidirectional audio streaming with Silero VAD.
- **Zero-Config Database**: Serverless SQLite database with automated migrations and AES-256-GCM envelope encryption.

---

## ⚙️ 1. Environment & Master Key Setup

Before running the platform, create your `.env` configuration file and generate a secure **Master Encryption Key (MEK)**. The platform uses AES-256-GCM envelope encryption to securely store API keys for providers (OpenAI, Deepgram, ElevenLabs, Fish Audio, etc.).

### Step A: Generate Master Encryption Key

Generate a 32-byte Base64-encoded key using Python or OpenSSL:

```bash
# Using Python
python3 -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"

# Or using OpenSSL
openssl rand -base64 32
```

### Step B: Create `.env`

Copy the example template and paste your generated master key:

```bash
cp .env.example .env
```

Open `.env` and set your key along with initial credentials:

```env
# ── Envelope Encryption (Required) ──
MASTER_ENCRYPTION_KEY=paste_your_generated_32_byte_base64_key_here

# ── Application & Security ──
APP_SECRET=dev-secret-change-in-production
ADMIN_API_KEY=admin-dev-key
ENVIRONMENT=development
PORT=8000
DB_PATH=data/widtts.db

# ── Realtime Transport (LiveKit) ──
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_INTERNAL_URL=ws://livekit:7880
LIVEKIT_API_KEY=devkey
LIVEKIT_API_SECRET=secret
LIVEKIT_TOKEN_TTL_SECONDS=3600
LIVEKIT_AUDIO_SAMPLE_RATE=16000
AGENT_TOKEN_TTL_SECONDS=7200
ROOM_INACTIVITY_TIMEOUT_SECONDS=60
```

---

## 🚀 2. Quick Start (Choose Any Method)

### Method 1: Local Manual Setup (No Docker required)

#### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **LiveKit Server** (`brew install livekit` or download binary from [LiveKit Releases](https://github.com/livekit/livekit/releases))

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

Runs LiveKit Server, Backend API, and Frontend UI in isolated containers.

```bash
# Ensure .env exists with your MASTER_ENCRYPTION_KEY first
docker compose up --build
```

* Frontend / Admin UI: **`http://localhost:3000`**
* Backend API: **`http://localhost:8000`**
* LiveKit WebRTC: **`ws://localhost:7880`**

---

### Method 3: Remote Tunneling with Ngrok

To expose your voice bot to mobile devices or remote users over WebRTC/HTTPS:

1. Add your ngrok authtoken to `.env`:
   ```bash
   NGROK_AUTHTOKEN=your_ngrok_token_here
   ```
2. Start the stack with the ngrok profile:
   ```bash
   docker compose --profile ngrok up --build
   ```
3. Check the public WebRTC and HTTP URLs from ngrok container logs:
   ```bash
   docker compose logs ngrok
   ```

---

## 🎛️ 3. Platform Setup in Admin Dashboard

Once the app is running:
1. Navigate to **`http://localhost:3000/admin`** (or click the Admin icon in the navigation bar).
2. Enter your `ADMIN_API_KEY` (configured in `.env`).
3. **Configure Speech & LLM Providers**: Add your API keys for:
   - **STT (Speech-to-Text)**: Deepgram / ElevenLabs
   - **TTS (Text-to-Speech)**: ElevenLabs / Fish Audio / Deepgram
   - **LLM (Language Model)**: OpenAI / Groq / Anthropic / OpenRouter / Custom endpoints
4. **Create & Activate a Bot**: Configure the system prompt, greetings, voice profiles, and set the bot to **Active**.
5. Return to the home screen and click **Connect / Speak** to start low-latency voice interaction!

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
