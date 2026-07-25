# Setup, Configuration & README

## Backend Setup

### requirements.txt

```
fastapi
uvicorn[standard]
pydantic-settings
python-dotenv
websockets
httpx
litellm
twilio
```

### .env.example

```
DEEPGRAM_API_KEY=your_deepgram_api_key_here
DATABASE_PATH=app.db
AI_VALIDATION_MODEL=claude-sonnet-4-6
MAX_RETRIES_PER_ITEM=3
```

### .gitignore

```
__pycache__/
*.pyc
*.pyo
.env
app.db
*.db-journal
venv/
.venv/
test_output.mp3
test_input.wav
```

### `__init__.py` Files

Every Python package directory requires an empty `__init__.py`. The full
list for the Modular Monolith + Clean Architecture structure:

```
backend/app/__init__.py

backend/app/shared/__init__.py
backend/app/shared/database/__init__.py
backend/app/shared/database/migrations/__init__.py
backend/app/shared/config/__init__.py
backend/app/shared/constants/__init__.py
backend/app/shared/logging/__init__.py
backend/app/shared/schemas/__init__.py
backend/app/shared/exceptions/__init__.py

backend/app/modules/__init__.py

backend/app/modules/session/__init__.py
backend/app/modules/session/domain/__init__.py
backend/app/modules/session/domain/entities/__init__.py
backend/app/modules/session/domain/interfaces/__init__.py
backend/app/modules/session/application/__init__.py
backend/app/modules/session/application/use_cases/__init__.py
backend/app/modules/session/infrastructure/__init__.py
backend/app/modules/session/infrastructure/persistence/__init__.py

backend/app/modules/message/__init__.py
backend/app/modules/message/domain/__init__.py
backend/app/modules/message/domain/entities/__init__.py
backend/app/modules/message/domain/interfaces/__init__.py
backend/app/modules/message/application/__init__.py
backend/app/modules/message/application/use_cases/__init__.py
backend/app/modules/message/infrastructure/__init__.py
backend/app/modules/message/infrastructure/persistence/__init__.py

backend/app/modules/conversation/__init__.py
backend/app/modules/conversation/domain/__init__.py
backend/app/modules/conversation/domain/entities/__init__.py
backend/app/modules/conversation/domain/interfaces/__init__.py
backend/app/modules/conversation/application/__init__.py
backend/app/modules/conversation/application/use_cases/__init__.py
backend/app/modules/conversation/application/services/__init__.py
backend/app/modules/conversation/infrastructure/__init__.py
backend/app/modules/conversation/infrastructure/persistence/__init__.py
backend/app/modules/conversation/infrastructure/external/__init__.py

backend/app/modules/voice/__init__.py
backend/app/modules/voice/domain/__init__.py
backend/app/modules/voice/domain/interfaces/__init__.py
backend/app/modules/voice/application/__init__.py
backend/app/modules/voice/application/use_cases/__init__.py
backend/app/modules/voice/infrastructure/__init__.py
backend/app/modules/voice/infrastructure/external/__init__.py

backend/app/modules/interruption/__init__.py
backend/app/modules/interruption/domain/__init__.py
backend/app/modules/interruption/domain/entities/__init__.py
backend/app/modules/interruption/domain/interfaces/__init__.py
backend/app/modules/interruption/application/__init__.py
backend/app/modules/interruption/application/use_cases/__init__.py
backend/app/modules/interruption/infrastructure/__init__.py
backend/app/modules/interruption/infrastructure/persistence/__init__.py

backend/app/entrypoints/__init__.py
backend/app/entrypoints/websocket/__init__.py
backend/app/entrypoints/http/__init__.py

backend/tests/__init__.py
backend/tests/modules/__init__.py
backend/tests/modules/session/__init__.py
backend/tests/modules/conversation/__init__.py
backend/tests/modules/interruption/__init__.py
backend/tests/shared/__init__.py
backend/tests/integration/__init__.py
```

---

## Frontend Setup

### package.json

```json
{
  "name": "conversational-widget-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.0",
    "vite": "^5.4.0"
  }
}
```

### vite.config.js

```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
  },
});
```

### .env.example (frontend)

```
VITE_WS_BASE_URL=ws://localhost:8000
```

### .gitignore (frontend)

```
node_modules/
dist/
.env
```

### index.html

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Conversational Widget</title>
</head>
<body>
  <div id="root"></div>
  <script type="module" src="/src/main.jsx"></script>
</body>
</html>
```

### src/main.jsx

```jsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
```

---

## README

```markdown
# Real-Time Conversational Widget Platform

A real-time voice conversational widget built with FastAPI and React,
using Deepgram for speech-to-text (STT) and text-to-speech (TTS), and
AI-assisted response validation.

## Architecture

**Backend:** Modular Monolith with Clean Architecture

The backend is organized as a single deployable unit composed of
self-contained feature modules. Each module follows Clean Architecture
principles with four layers:

| Layer            | Responsibility                                          |
|------------------|---------------------------------------------------------|
| **Domain**       | Entities, interfaces/contracts, value objects            |
| **Application**  | Use cases (classes with `execute()`), orchestration      |
| **Infrastructure** | SQLite repositories, Deepgram adapters, Anthropic client |
| **Presentation** | FastAPI WebSocket handler, HTTP endpoints                |

Dependencies always point inward toward the Domain layer. Infrastructure
implements Domain interfaces. The Domain never depends on frameworks or
external services.

**Modules:**
- `session` — session lifecycle management
- `message` — transcript message persistence
- `conversation` — scripted conversation flow, AI validation
- `voice` — Deepgram STT/TTS integration
- `interruption` — interruption detection and recording

**Shared:** database, config, constants, logging, schemas, exceptions

**Frontend:** React with Context + useReducer, WebSocket communication

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLite
- **Frontend:** React 18, Vite 5
- **Voice:** Deepgram (STT + TTS)
- **AI Validation:** Anthropic API (Claude)
- **Communication:** WebSocket only

## Getting Started

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate     # macOS/Linux
# venv\Scripts\activate      # Windows
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Deepgram API key
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

### Verify

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

## Project Structure

```
backend/
  app/
    modules/          # Self-contained feature modules
      session/        # Session lifecycle management
      message/        # Transcript message persistence
      conversation/   # Scripted conversation flow, AI validation
      voice/          # Deepgram STT/TTS integration
      interruption/   # Interruption detection and recording
    shared/           # Cross-cutting concerns
      database/       # SQLite connection, migrations
      config/         # Application settings
      constants/      # Conversation types, states, interruption types
      logging/        # Shared logger
      schemas/        # Pydantic schemas
      exceptions/     # Domain exceptions
    entrypoints/      # Presentation layer
      websocket/      # WebSocket handler + connection manager
      http/           # Health endpoint
  tests/
  main.py

frontend/
  src/
    components/       # React components
    hooks/            # Custom hooks (WebSocket, audio)
    services/         # WebSocket service
    context/          # State management (Context + useReducer)
    pages/            # Page components
    utils/            # Audio utilities
    App.jsx
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| WS | `/ws/{conversation_type}/{session_id}` | Conversational WebSocket |

## Conversation Types

- `daily_life_companion` (30 questions)
- `career_life_advisor` (35 questions)
- `health_wellness_assistant` (35 questions)
- `travel_planner` (35 questions)

## License

Private / Internal
```
