# widTTS — Voice Platform

A state-of-the-art, real-time AI voice assistant platform built using Clean Architecture on the backend (FastAPI, PostgreSQL, LiveKit Agents, LiteLLM) and a modern 3D interactive visualizer on the frontend (React 18, Three.js / React Three Fiber, Vite 5, Tailwind CSS, Framer Motion).

---

## 🏗️ Architectural Overview

* **Zero Hardcoding Policy**: All LLM, Speech (STT/TTS), and Realtime Transport settings are managed dynamically via PostgreSQL using Envelope Encryption (AES-256-GCM). No provider secrets or server endpoints exist in application code.
* **LiveKit Infrastructure Integration**: Realtime WebRTC audio processing runs entirely server-side via official LiveKit plugins (`livekit-plugins-silero` VAD, `livekit-plugins-deepgram`, `livekit-plugins-elevenlabs`).
* **Single Seam LLM Bridge**: widTTS integrates with LiveKit via a custom `WidTTSLLMBridge` implementing `livekit.agents.llm.LLM`. It enforces business policies (STOP/REPEAT/CORRECTION/END) before delegating token streaming to the bot's configured LLM.
* **Continuous 3D Admin Journey**: Admin portal features a 7-stage interactive 3D scroll experience (`Overview` → `LLM` → `Realtime` → `Speech` → `Bot` → `Activate` → `Live`) with glassmorphism UI, real-time connection verification, and multi-provider selection.

---

## 📂 Repository Structure

```
widTts/
├── backend/                  # FastAPI Modular Monolith (Clean Architecture)
│   ├── app/
│   │   ├── entrypoints/      # HTTP REST APIs (Admin, Realtime Token, Health)
│   │   ├── modules/          # Domain, Application, Infrastructure modules (bot, conversation, provider, session, voice)
│   │   └── shared/           # Database, Envelope Encryption, Event Bus, Structured Logging
│   ├── tests/                # Automated pytest suite (84 tests)
│   ├── requirements.txt      # Python dependencies (livekit-agents, livekit-api, etc.)
│   └── main.py               # FastAPI application entrypoint with startup validation
├── frontend/                 # React 18 SPA (Vite 5)
│   ├── src/
│   │   ├── components/       # 3D Journey, HolographicOrb, Controls, Glass UI
│   │   ├── context/          # ConversationContext state management
│   │   ├── hooks/            # useLiveKitRoom, useVoiceSession
│   │   └── pages/            # HomePage (User Voice Widget), AdminJourney
│   └── package.json          # Frontend dependencies (livekit-client, three, etc.)
├── docker-compose.yml        # Local PostgreSQL (5432) + LiveKit Server (7880)
├── livekit.yaml              # Local LiveKit OSS configuration
└── readme.md                 # Technical setup & developer guide
```

---

## 🔑 Obtaining LiveKit API Keys

### Option A: Local Development (Docker Container)

When running the local Docker container (`docker-compose up -d`), LiveKit operates in local development mode with pre-configured keys defined in `livekit.yaml`:

* **Server URL**: `ws://localhost:7880`
* **API Key**: `devkey`
* **API Secret**: `secret`

> **Note**: No registration or internet connection is required for local Docker mode.

---

### Option B: LiveKit Cloud (Production / Staging)

To connect widTTS to a cloud-managed LiveKit server:

1. Sign up or log into [cloud.livekit.io](https://cloud.livekit.io).
2. Create a new Project (or select your existing project).
3. In the left navigation, go to **Project Settings → Keys**.
4. Copy the following credentials from your dashboard:
   * **WebSocket URL**: `wss://your-project-subdomain.livekit.cloud`
   * **API Key**: `APIxxxxxxxxxxxx`
   * **API Secret**: `secretxxxxxxxxxxxxxxxx`
5. Configure these credentials in `backend/.env` under `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`.

---

## ⚡ Quick Start & Execution Guide

### Step 1: Start Background Services (Docker)

Start the local PostgreSQL database and LiveKit OSS server:

```bash
# From the project root directory:
docker-compose up -d
```

This starts:
* **PostgreSQL**: `localhost:5432` (database: `widtts`, user: `widtts`, password: `widtts_dev_password`)
* **LiveKit Server**: `localhost:7880` (RTC port range `50000-50100`)

---

### Step 2: Configure & Start the Backend

1. **Environment File (`backend/.env`)**:
   Verify or create `backend/.env`:

   ```env
   POSTGRES_USER=widtts
   POSTGRES_PASSWORD=widtts_dev_password
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=widtts

   DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
   MASTER_ENCRYPTION_KEY=PGe4qntNrj9RGqhna1JwmRfjm7WPr2e2njV6fT3r8PM=
   APP_SECRET=dev-secret-change-in-production
   PORT=8000

   # LiveKit Realtime Transport
   LIVEKIT_URL=ws://localhost:7880
   LIVEKIT_API_KEY=devkey
   LIVEKIT_API_SECRET=secret
   LIVEKIT_TOKEN_TTL_SECONDS=3600
   LIVEKIT_AUDIO_SAMPLE_RATE=16000
   ```

   *(To generate a new 32-byte Master Encryption Key, run: `python3 -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"`)*

2. **Install Dependencies & Launch Server**:

   ```bash
   cd backend

   # Activate virtual environment
   source venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt

   # Start the FastAPI backend server
   uvicorn main:app --reload --port 8000
   ```

   * Backend health check endpoint: `http://localhost:8000/health`

---

### Step 3: Start the Frontend Application

Open a separate terminal window and execute:

```bash
cd frontend

# Install packages
npm install

# Start Vite developer server
npm run dev
```

* The application will run locally at **`http://localhost:3000/`**.

---

## 🛠️ Configuring Providers & Activating a Bot

1. Open `http://localhost:3000/` in your browser and click **Enter as Admin**.
2. **Step 1 (LLM)**: Add an LLM provider (e.g. OpenAI, Anthropic, or OpenAI-Compatible) and enter your API key.
3. **Step 2 (Realtime)**: Click **Realtime Transport**:
   * For **Local Docker**: Server URL `ws://localhost:7880`, API Key `devkey`, API Secret `secret`.
   * For **LiveKit Cloud**: Server URL `wss://your-subdomain.livekit.cloud`, API Key `APIxxx`, API Secret `secretxxx`.
   * Click **Test Connection** to verify handshake, then **Save Transport Provider**.
4. **Step 3 (Speech)**: Add a speech provider (Deepgram or ElevenLabs) with STT/TTS models.
5. **Step 4 (Bot)**: Select the configured LLM, Speech Provider, system prompt, and voice ID, then click **Create AI Bot**.
6. **Step 5 (Activate)**: Click **Activate Bot** to make it active for all sessions.
7. **Test User Experience**: Navigate to `http://localhost:3000/user` to interact with your live AI voice bot!

---

## 🧪 Verification & Testing

### Running Backend Tests

The backend contains a comprehensive unit and integration test suite:

```bash
cd backend
venv/bin/pytest tests/ -v
```

### Building Frontend Production Bundle

```bash
cd frontend
npm run build
```
