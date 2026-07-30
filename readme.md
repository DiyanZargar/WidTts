# Real-Time Voice Conversational Platform

A premium, immersive real-time voice assistant experience using Clean Architecture on the backend (FastAPI, SQLite, Deepgram, LiteLLM) and a modern 3D visualizer on the frontend (React 18, Vite 5, Tailwind CSS, Framer Motion).

---

## 📂 Project Structure

* **`backend/`**: FastAPI Modular Monolith (Clean Architecture).
* **`frontend/`**: React SPA dev-server.
* **`codebase_study.md`**: Exhaustive step-by-step developer reading guide mapping imports, classes, call chains, and state loops.

---

## ⚡ Setup & Execution

### 1. Environment Setup

Configure your local credentials in both the backend and frontend configurations.

* **Backend `.env`**: Make sure `backend/.env` is populated with the following fields:
  ```env
  DEEPGRAM_API_KEY=your_deepgram_api_key_here
  DEEPGRAM_TTS_MODEL=aura-2-thalia-en
  DEEPGRAM_STT_URL=wss://api.deepgram.com/v1/listen?punctuate=true&interim_results=true
  
  OPENAI_API_KEY=your_openai_api_key_here
  OPENAI_BASE_URL=https://api.openai.com/v1
  AI_VALIDATION_MODEL=gemini/gemini-2.5-flash
  
  DATABASE_PATH=app.db
  CONVERSATION_DEFINITIONS_DIR=app/conversation_definitions
  ```

* **Frontend `.env`**: Make sure `frontend/.env` is populated:
  ```env
  VITE_WS_BASE_URL=ws://localhost:8000
  ```

---

### 2. Running the Backend

Open a terminal window and execute:

```bash
cd backend

# Initialize the environment (if not already done)
source venv/bin/activate
pip install -r requirements.txt

# Start the uvicorn development server
venv/bin/uvicorn main:app --reload --port 8000
```

* The backend handles automatic startup migrations and compiles the in-memory cached JSON conversation matrices dynamically.
* API health check details are visible at `http://localhost:8000/health`.

---

### 3. Running the Frontend

Open a separate terminal window and execute:

```bash
cd frontend

# Install node packages (if not already done)
npm install

# Start the Vite developer server
npm run dev
```

* The developer dashboard runs locally at **`http://localhost:3000/`**.

---

## 🧪 Running Automated Tests

To verify backend database tables, dynamic schemas, and WebSocket authorization handshakes, run:

```bash
cd backend
venv/bin/pytest tests/ -v
```
