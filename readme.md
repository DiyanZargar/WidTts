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

* **Backend `.env`**: Make sure `backend/.env` is populated:
  ```env
  POSTGRES_USER=widtts
  POSTGRES_PASSWORD=widtts_dev_password
  POSTGRES_HOST=localhost
  POSTGRES_PORT=5432
  POSTGRES_DB=widtts

  DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}
  MASTER_ENCRYPTION_KEY=PGe4qntNrj9RGqhna1JwmRfjm7WPr2e2njV6fT3r8PM=
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
