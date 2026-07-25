# Complete End-to-End Build Roadmap & Final Architecture Synchronization

This roadmap reflects all final architecture decisions and provides step-by-step instructions with complete, un-truncated code blocks for every file in the system.

---

## 📌 Summary of Architecture Synchronizations

| Architectural Area | Final Synchronized Design | Architectural Impact |
|---|---|---|
| **1. JSON Definitions** | **Single Source of Truth**. Stored in `app/conversation_definitions/` (`daily_life.json`, `career_life.json`, `health_wellness.json`, `travel_planner.json`). | `ConversationEngine` contains ZERO conversation data and ZERO database logic. Definitions are loaded strictly from JSON files in Infrastructure. |
| **2. Questions Table Removed** | **Removed**. Deleted `questions` table, seeding, `QuestionEntity`, and `QuestionRepository`. | SQLite stores ONLY runtime state (`sessions`, `messages`, `responses`, `interruptions`). Definitions never touch SQLite. |
| **3. Responses Table Schema** | **Updated**. Replaced `question_id` with `sequence` (integer matching JSON definition sequence). | `responses` references the JSON sequence index rather than a database row ID. |
| **4. LiteLLM Validation** | **Clean Architecture Enforced**. Created `ValidationProviderInterface` in Domain layer. | `ValidateResponse` depends on interface; `LiteLLMValidationAdapter` in Infrastructure implements it. |
| **5. Backend-Owned Session ID** | **Implemented**. Route: `WS /ws/{conversation_type}`. | Backend generates UUID v4 at connection, returns it in `session_started` event. Recovery uses `?session_id={id}` query param. |
| **6. PAUSED Session State** | **Implemented**. State machine: `ACTIVE ↔ PAUSED → COMPLETED / CANCELLED`. | On `WebSocketDisconnect`, session transitions to `PAUSED`. Reconnecting with `?session_id={id}` reloads past transcript (`get_by_session`) and resumes pointer. |
| **7. Subtitle Transcript UI** | **Directly in Widget Window**. Removed separate transcript components (`Transcript.jsx`, `TranscriptOverlay.jsx`). | Plain-text live subtitles (last 6 lines, partial replacement, auto-scroll) are rendered directly inside `ConversationWindow.jsx`. |
| **8. Audio Pipeline** | **Direct FastAPI Streaming**. Audio flows `Client → FastAPI → Deepgram STT/TTS`. | No Twilio media stream hop. Unnecessary overhead eliminated. |

---

## 📋 Table of Contents

1. [Phase A: System Prerequisites & Environment Setup](#phase-a)
2. [Phase B: Project Skeleton & Directory Creation](#phase-b)
3. [Phase C: Shared Layer & Database Migrations](#phase-c)
4. [Phase D: Session Module (With PAUSED State & Backend Session ID)](#phase-d)
5. [Phase E: Message Module (With Transcript Recovery)](#phase-e)
6. [Phase F: Conversation Module (JSON Source of Truth & Engine)](#phase-f)
7. [Phase G: Voice Module (Deepgram Streaming STT & TTS)](#phase-g)
8. [Phase H: Interruption Module](#phase-h)
9. [Phase I: Presentation Entrypoints & WebSocket Handler](#phase-i)
10. [Phase J: Application Assembly (`main.py`)](#phase-j)
11. [Phase K: Backend Test Suite](#phase-k)
12. [Phase L: React Frontend Application](#phase-l)
13. [Phase M: End-to-End Verification](#phase-m)

---

<a id="phase-a"></a>
## Phase A: System Prerequisites & Environment Setup

### Step A.1 — Check System Dependencies

Ensure **Python 3.11+** and **Node.js 18+** are installed:

```bash
python3 --version
node --version
npm --version
```

### Step A.2 — Create Workspace Directories

From your project workspace root:

```bash
mkdir -p backend frontend
```

### Step A.3 — Setup Backend Virtual Environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate    # macOS/Linux
# venv\Scripts\activate     # Windows
```

### Step A.4 — Write `requirements.txt`

Create `backend/requirements.txt`:

```text
fastapi
uvicorn[standard]
pydantic-settings
python-dotenv
websockets
httpx
litellm
pytest
pytest-asyncio
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### Step A.5 — Configure Environment Variables

Create `backend/.env.example`:

```env
DEEPGRAM_API_KEY=your_deepgram_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here
DATABASE_PATH=app.db
AI_VALIDATION_MODEL=claude-sonnet-4-6
MAX_RETRIES_PER_ITEM=3
```

Create `backend/.env` (replace with your actual API keys):

```bash
cp .env.example .env
```

### Step A.6 — Backend `.gitignore`

Create `backend/.gitignore`:

```text
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

---

<a id="phase-b"></a>
## Phase B: Project Skeleton & Directory Creation

Execute these commands inside `backend/` to build the Clean Architecture folder structure:

```bash
# Conversation Definitions (JSON Packs)
mkdir -p app/conversation_definitions

# Shared Layer
mkdir -p app/shared/database/migrations
mkdir -p app/shared/config
mkdir -p app/shared/constants
mkdir -p app/shared/logging
mkdir -p app/shared/schemas
mkdir -p app/shared/exceptions

# Modules
mkdir -p app/modules/session/domain/entities
mkdir -p app/modules/session/domain/interfaces
mkdir -p app/modules/session/application/use_cases
mkdir -p app/modules/session/infrastructure/persistence

mkdir -p app/modules/message/domain/entities
mkdir -p app/modules/message/domain/interfaces
mkdir -p app/modules/message/application/use_cases
mkdir -p app/modules/message/infrastructure/persistence

mkdir -p app/modules/conversation/domain/entities
mkdir -p app/modules/conversation/domain/interfaces
mkdir -p app/modules/conversation/application/use_cases
mkdir -p app/modules/conversation/application/services
mkdir -p app/modules/conversation/infrastructure/persistence
mkdir -p app/modules/conversation/infrastructure/external

mkdir -p app/modules/voice/domain/interfaces
mkdir -p app/modules/voice/application/use_cases
mkdir -p app/modules/voice/infrastructure/external

mkdir -p app/modules/interruption/domain/entities
mkdir -p app/modules/interruption/domain/interfaces
mkdir -p app/modules/interruption/application/use_cases
mkdir -p app/modules/interruption/infrastructure/persistence

# Entrypoints
mkdir -p app/entrypoints/websocket
mkdir -p app/entrypoints/http

# Tests
mkdir -p tests/modules/session
mkdir -p tests/modules/conversation
mkdir -p tests/modules/interruption
mkdir -p tests/shared
mkdir -p tests/integration
```

Create all `__init__.py` files:

```bash
touch app/__init__.py
touch app/shared/__init__.py app/shared/database/__init__.py app/shared/database/migrations/__init__.py
touch app/shared/config/__init__.py app/shared/constants/__init__.py app/shared/logging/__init__.py
touch app/shared/schemas/__init__.py app/shared/exceptions/__init__.py
touch app/modules/__init__.py
touch app/modules/session/__init__.py app/modules/session/domain/__init__.py app/modules/session/domain/entities/__init__.py app/modules/session/domain/interfaces/__init__.py app/modules/session/application/__init__.py app/modules/session/application/use_cases/__init__.py app/modules/session/infrastructure/__init__.py app/modules/session/infrastructure/persistence/__init__.py
touch app/modules/message/__init__.py app/modules/message/domain/__init__.py app/modules/message/domain/entities/__init__.py app/modules/message/domain/interfaces/__init__.py app/modules/message/application/__init__.py app/modules/message/application/use_cases/__init__.py app/modules/message/infrastructure/__init__.py app/modules/message/infrastructure/persistence/__init__.py
touch app/modules/conversation/__init__.py app/modules/conversation/domain/__init__.py app/modules/conversation/domain/entities/__init__.py app/modules/conversation/domain/interfaces/__init__.py app/modules/conversation/application/__init__.py app/modules/conversation/application/use_cases/__init__.py app/modules/conversation/application/services/__init__.py app/modules/conversation/infrastructure/__init__.py app/modules/conversation/infrastructure/persistence/__init__.py app/modules/conversation/infrastructure/external/__init__.py
touch app/modules/voice/__init__.py app/modules/voice/domain/__init__.py app/modules/voice/domain/interfaces/__init__.py app/modules/voice/application/__init__.py app/modules/voice/application/use_cases/__init__.py app/modules/voice/infrastructure/__init__.py app/modules/voice/infrastructure/external/__init__.py
touch app/modules/interruption/__init__.py app/modules/interruption/domain/__init__.py app/modules/interruption/domain/interfaces/__init__.py app/modules/interruption/application/__init__.py app/modules/interruption/application/use_cases/__init__.py app/modules/interruption/infrastructure/__init__.py app/modules/interruption/infrastructure/persistence/__init__.py
touch app/entrypoints/__init__.py app/entrypoints/websocket/__init__.py app/entrypoints/http/__init__.py
touch tests/__init__.py tests/modules/__init__.py tests/modules/session/__init__.py tests/modules/conversation/__init__.py tests/modules/interruption/__init__.py tests/shared/__init__.py tests/integration/__init__.py
```

---

<a id="phase-c"></a>
## Phase C: Shared Layer & Database Migrations

### Step C.1 — `app/shared/config/settings.py`

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    deepgram_api_key: str
    anthropic_api_key: str = ""
    database_path: str = "app.db"
    ai_validation_model: str = "claude-sonnet-4-6"
    max_retries_per_item: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
```

### Step C.2 — `app/shared/database/db.py`

```python
import sqlite3
from contextlib import contextmanager
from app.shared.config.settings import settings


@contextmanager
def get_connection():
    conn = sqlite3.connect(settings.database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
```

### Step C.3 — Database Migrations (`app/shared/database/migrations/`)

SQLite stores **ONLY** runtime state (`sessions`, `messages`, `responses`, `interruptions`). Definitions never touch SQLite.

`0001_create_sessions_table.sql`:
```sql
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    conversation_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    current_question_index INTEGER NOT NULL DEFAULT 0,
    current_state TEXT NOT NULL DEFAULT 'welcoming',
    retries INTEGER NOT NULL DEFAULT 0
);
```

`0002_create_messages_table.sql`:
```sql
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    sender TEXT NOT NULL CHECK (sender IN ('system','user')),
    text TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

`0003_create_responses_table.sql`:
```sql
CREATE TABLE IF NOT EXISTS responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    sequence INTEGER NOT NULL,
    user_response TEXT NOT NULL,
    validation_result TEXT NOT NULL CHECK (validation_result IN ('valid','invalid'))
);
```

`0004_create_interruptions_table.sql`:
```sql
CREATE TABLE IF NOT EXISTS interruptions (
    interruption_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    interruption_type TEXT NOT NULL CHECK (interruption_type IN ('stop','cancel','repeat','correction')),
    interruption_text TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

`0005_add_status_index_to_sessions.sql`:
```sql
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
```

### Step C.4 — `app/shared/database/migrations/runner.py`

```python
import os
import sqlite3
from app.shared.config.settings import settings


def run_migrations():
    migration_dir = os.path.join(os.path.dirname(__file__))
    conn = sqlite3.connect(settings.database_path)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()

    applied = {
        row[0]
        for row in conn.execute("SELECT filename FROM schema_migrations").fetchall()
    }

    sql_files = sorted(f for f in os.listdir(migration_dir) if f.endswith(".sql"))

    for filename in sql_files:
        if filename in applied:
            continue
        filepath = os.path.join(migration_dir, filename)
        with open(filepath, "r") as f:
            sql = f.read()
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (filename) VALUES (?)", (filename,)
        )
        conn.commit()
        print(f"Applied migration: {filename}")

    conn.close()
```

### Step C.5 — `app/shared/database/init_db.py`

```python
from app.shared.database.migrations.runner import run_migrations


def init_db():
    run_migrations()
```

---

<a id="phase-d"></a>
## Phase D: Session Module (With PAUSED State & Backend Session ID)

### Step D.1 — Domain Entity: `app/modules/session/domain/entities/session_entity.py`

```python
from dataclasses import dataclass


@dataclass
class Session:
    session_id: str
    start_time: str
    end_time: str | None
    conversation_type: str
    status: str  # 'active' | 'paused' | 'completed' | 'cancelled'
    current_question_index: int
    current_state: str
    retries: int
```

### Step D.2 — Repository Interface: `app/modules/session/domain/interfaces/session_repository_interface.py`

```python
from abc import ABC, abstractmethod


class SessionRepositoryInterface(ABC):

    @abstractmethod
    def create(self, session_id: str, conversation_type: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, session_id: str) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def update_pointer(self, session_id: str, index: int, state: str, retries: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def pause(self, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self, session_id: str, status: str) -> None:
        raise NotImplementedError
```

### Step D.3 — Infrastructure Adapter: `app/modules/session/infrastructure/persistence/sqlite_session_repository.py`

```python
from datetime import datetime, timezone
from app.shared.database.db import get_connection
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class SqliteSessionRepository(SessionRepositoryInterface):

    def create(self, session_id: str, conversation_type: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, start_time, conversation_type, status) VALUES (?, ?, ?, 'active')",
                (session_id, datetime.now(timezone.utc).isoformat(), conversation_type),
            )

    def get_by_id(self, session_id: str) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_pointer(self, session_id: str, index: int, state: str, retries: int) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET current_question_index=?, current_state=?, retries=?, status='active' WHERE session_id=?",
                (index, state, retries, session_id),
            )

    def pause(self, session_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET status='paused' WHERE session_id=? AND status='active'",
                (session_id,),
            )

    def close(self, session_id: str, status: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET status=?, end_time=?, current_state='completed' WHERE session_id=?",
                (status, datetime.now(timezone.utc).isoformat(), session_id),
            )
```

### Step D.4 — Application Use Cases

`app/modules/session/application/use_cases/create_session.py`:
```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class CreateSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, conversation_type: str) -> None:
        self._session_repository.create(session_id, conversation_type)
```

`app/modules/session/application/use_cases/get_session.py`:
```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class GetSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str) -> dict | None:
        return self._session_repository.get_by_id(session_id)
```

`app/modules/session/application/use_cases/update_pointer.py`:
```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class UpdatePointer:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, index: int, state: str, retries: int) -> None:
        self._session_repository.update_pointer(session_id, index, state, retries)
```

`app/modules/session/application/use_cases/pause_session.py`:
```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class PauseSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str) -> None:
        self._session_repository.pause(session_id)
```

`app/modules/session/application/use_cases/close_session.py`:
```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class CloseSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, status: str) -> None:
        self._session_repository.close(session_id, status)
```

---

<a id="phase-e"></a>
## Phase E: Message Module (With Transcript Recovery)

### Step E.1 — Domain Entity: `app/modules/message/domain/entities/message_entity.py`

```python
from dataclasses import dataclass


@dataclass
class Message:
    session_id: str
    sender: str  # 'system' | 'user'
    text: str
    timestamp: str
```

### Step E.2 — Interface: `app/modules/message/domain/interfaces/message_repository_interface.py`

```python
from abc import ABC, abstractmethod


class MessageRepositoryInterface(ABC):

    @abstractmethod
    def add(self, session_id: str, sender: str, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_by_session(self, session_id: str) -> list[dict]:
        raise NotImplementedError
```

### Step E.3 — Adapter: `app/modules/message/infrastructure/persistence/sqlite_message_repository.py`

```python
from datetime import datetime, timezone
from app.shared.database.db import get_connection
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface


class SqliteMessageRepository(MessageRepositoryInterface):

    def add(self, session_id: str, sender: str, text: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, sender, text, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, sender, text, datetime.now(timezone.utc).isoformat()),
            )

    def get_by_session(self, session_id: str) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT sender, text, timestamp FROM messages WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
```

### Step E.4 — Use Cases

`app/modules/message/application/use_cases/add_message.py`:
```python
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface


class AddMessage:

    def __init__(self, message_repository: MessageRepositoryInterface):
        self._message_repository = message_repository

    def execute(self, session_id: str, sender: str, text: str) -> None:
        self._message_repository.add(session_id, sender, text)
```

`app/modules/message/application/use_cases/get_messages.py`:
```python
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface


class GetMessages:

    def __init__(self, message_repository: MessageRepositoryInterface):
        self._message_repository = message_repository

    def execute(self, session_id: str) -> list[dict]:
        return self._message_repository.get_by_session(session_id)
```

---

<a id="phase-f"></a>
## Phase F: Conversation Module (JSON Source of Truth & Engine)

### Step F.1 — JSON Conversation Definitions (`app/conversation_definitions/`)

JSON files are the **ONLY** source of truth for conversation packs.

`app/conversation_definitions/daily_life.json`:
```json
{
  "intro_line": "I'd love to know how your day is going.",
  "questions": [
    {"sequence": 0, "type": "question", "text": "What should I call you?", "expected_context": "a name or preferred nickname"},
    {"sequence": 1, "type": "question", "text": "What time did you wake up today?", "expected_context": "a wake-up time"},
    {"sequence": 2, "type": "question", "text": "Did you sleep well?", "expected_context": "a description of sleep quality"},
    {"sequence": 3, "type": "question", "text": "What was the first thing you did this morning?", "expected_context": "an activity done after waking"},
    {"sequence": 4, "type": "question", "text": "Did you have breakfast?", "expected_context": "yes/no or a description of breakfast"},
    {"sequence": 5, "type": "question", "text": "How are you feeling right now?", "expected_context": "a current mood or feeling"},
    {"sequence": 6, "type": "question", "text": "How would you rate today so far?", "expected_context": "a rating or descriptive assessment of the day"},
    {"sequence": 7, "type": "question", "text": "What are you working on today?", "expected_context": "a task, project, or activity"},
    {"sequence": 8, "type": "question", "text": "What's your biggest priority?", "expected_context": "a stated priority or focus"},
    {"sequence": 9, "type": "question", "text": "Is anything stressing you out?", "expected_context": "yes/no or a source of stress"},
    {"sequence": 10, "type": "question", "text": "Have you talked to anyone interesting today?", "expected_context": "yes/no or a description of a conversation"},
    {"sequence": 11, "type": "question", "text": "Have you learned something new recently?", "expected_context": "yes/no or a new fact or skill learned"},
    {"sequence": 12, "type": "question", "text": "Did anything make you smile today?", "expected_context": "yes/no or a positive moment"},
    {"sequence": 13, "type": "question", "text": "Did anything frustrate you today?", "expected_context": "yes/no or a frustrating moment"},
    {"sequence": 14, "type": "question", "text": "How productive have you been?", "expected_context": "a productivity level description"},
    {"sequence": 15, "type": "question", "text": "What task have you been avoiding?", "expected_context": "a task being avoided"},
    {"sequence": 16, "type": "question", "text": "What's distracting you lately?", "expected_context": "a source of distraction"},
    {"sequence": 17, "type": "question", "text": "What's one thing you'd like to accomplish before the day ends?", "expected_context": "a goal for the rest of the day"},
    {"sequence": 18, "type": "question", "text": "Are you happy with how you're spending your time?", "expected_context": "yes/no with optional reasoning"},
    {"sequence": 19, "type": "question", "text": "If you had an extra hour today, what would you do?", "expected_context": "a hypothetical activity"},
    {"sequence": 20, "type": "question", "text": "What are you grateful for today?", "expected_context": "something the user is grateful for"},
    {"sequence": 21, "type": "question", "text": "What is something you're looking forward to?", "expected_context": "an upcoming event or moment"},
    {"sequence": 22, "type": "question", "text": "What's currently on your mind?", "expected_context": "a current thought or concern"},
    {"sequence": 23, "type": "question", "text": "Is there anything bothering you?", "expected_context": "yes/no or a concern"},
    {"sequence": 24, "type": "question", "text": "What's the best thing that happened this week?", "expected_context": "a positive event from this week"},
    {"sequence": 25, "type": "question", "text": "What's your plan for tomorrow?", "expected_context": "a plan or intention for tomorrow"},
    {"sequence": 26, "type": "question", "text": "What's one thing you'd like to improve about yourself?", "expected_context": "a personal improvement area"},
    {"sequence": 27, "type": "question", "text": "Is there someone you'd like to reconnect with?", "expected_context": "yes/no or a person's name or relation"},
    {"sequence": 28, "type": "question", "text": "If today had a title, what would it be?", "expected_context": "a short title or phrase describing the day"},
    {"sequence": 29, "type": "question", "text": "Is there anything you'd like my help with before we end?", "expected_context": "yes/no or a request for help"}
  ]
}
```

`app/conversation_definitions/career_life.json`:
```json
{
  "intro_line": "Let's talk about your career, goals, and where you'd like to go in life.",
  "questions": [
    {"sequence": 0, "type": "question", "text": "What should I call you?", "expected_context": "a name or preferred nickname"},
    {"sequence": 1, "type": "question", "text": "How old are you?", "expected_context": "an age"},
    {"sequence": 2, "type": "question", "text": "Where are you currently living?", "expected_context": "a city, region, or country"},
    {"sequence": 3, "type": "question", "text": "What do you do for a living?", "expected_context": "a job title or occupation"},
    {"sequence": 4, "type": "question", "text": "Are you satisfied with your current role?", "expected_context": "yes/no with optional reasoning"},
    {"sequence": 5, "type": "question", "text": "What is your dream job?", "expected_context": "a job title or career description"},
    {"sequence": 6, "type": "question", "text": "Why does it appeal to you?", "expected_context": "a reason or motivation"},
    {"sequence": 7, "type": "question", "text": "How many years of experience do you have?", "expected_context": "a number of years"},
    {"sequence": 8, "type": "question", "text": "What skills are you strongest in?", "expected_context": "one or more named skills"},
    {"sequence": 9, "type": "question", "text": "Which skill would you like to improve?", "expected_context": "a named skill"},
    {"sequence": 10, "type": "question", "text": "What's the biggest project you've worked on?", "expected_context": "a description of a project"},
    {"sequence": 11, "type": "question", "text": "Have you ever managed a team?", "expected_context": "yes/no with optional detail"},
    {"sequence": 12, "type": "question", "text": "Startup or enterprise?", "expected_context": "a stated preference between startup and enterprise"},
    {"sequence": 13, "type": "question", "text": "Remote or office?", "expected_context": "a stated preference between remote and office"},
    {"sequence": 14, "type": "question", "text": "Which companies would you love to work for?", "expected_context": "one or more company names"},
    {"sequence": 15, "type": "question", "text": "What are you learning right now?", "expected_context": "a skill or subject currently being learned"},
    {"sequence": 16, "type": "question", "text": "What is your biggest career goal?", "expected_context": "a stated career goal"},
    {"sequence": 17, "type": "question", "text": "What's preventing you from reaching it?", "expected_context": "an obstacle or barrier"},
    {"sequence": 18, "type": "question", "text": "What motivates you?", "expected_context": "a source of motivation"},
    {"sequence": 19, "type": "question", "text": "What usually distracts you?", "expected_context": "a source of distraction"},
    {"sequence": 20, "type": "question", "text": "What does success mean to you?", "expected_context": "a personal definition of success"},
    {"sequence": 21, "type": "question", "text": "Where do you see yourself in one year?", "expected_context": "a one-year outlook"},
    {"sequence": 22, "type": "question", "text": "Five years?", "expected_context": "a five-year outlook"},
    {"sequence": 23, "type": "question", "text": "Ten years?", "expected_context": "a ten-year outlook"},
    {"sequence": 24, "type": "question", "text": "Do you want financial freedom, recognition, or impact?", "expected_context": "a stated priority among financial freedom, recognition, or impact"},
    {"sequence": 25, "type": "question", "text": "If money weren't a factor, what would you do?", "expected_context": "a hypothetical career or life choice"},
    {"sequence": 26, "type": "question", "text": "What's your greatest achievement?", "expected_context": "a described achievement"},
    {"sequence": 27, "type": "question", "text": "What's your biggest regret?", "expected_context": "a described regret"},
    {"sequence": 28, "type": "question", "text": "Who inspires you?", "expected_context": "a person or type of person"},
    {"sequence": 29, "type": "question", "text": "What's one thing you'd tell your younger self?", "expected_context": "a piece of advice"},
    {"sequence": 30, "type": "question", "text": "What habit would you like to develop?", "expected_context": "a named habit"},
    {"sequence": 31, "type": "question", "text": "What habit would you like to eliminate?", "expected_context": "a named habit"},
    {"sequence": 32, "type": "question", "text": "What are you most proud of?", "expected_context": "a source of pride"},
    {"sequence": 33, "type": "question", "text": "What's your biggest fear about the future?", "expected_context": "a described fear"},
    {"sequence": 34, "type": "question", "text": "What would make you feel fulfilled?", "expected_context": "a description of fulfillment"}
  ]
}
```

`app/conversation_definitions/health_wellness.json`:
```json
{
  "intro_line": "Let's talk about your health and how you're feeling.",
  "questions": [
    {"sequence": 0, "type": "question", "text": "What should I call you?", "expected_context": "a name or preferred nickname"},
    {"sequence": 1, "type": "question", "text": "How old are you?", "expected_context": "an age"},
    {"sequence": 2, "type": "question", "text": "What's your height?", "expected_context": "a height measurement"},
    {"sequence": 3, "type": "question", "text": "What's your weight?", "expected_context": "a weight measurement"},
    {"sequence": 4, "type": "question", "text": "What do you do for work?", "expected_context": "a job title or occupation"},
    {"sequence": 5, "type": "question", "text": "How would you rate your health?", "expected_context": "a self-rated health assessment"},
    {"sequence": 6, "type": "question", "text": "Do you have any medical conditions?", "expected_context": "yes/no or named condition(s)"},
    {"sequence": 7, "type": "question", "text": "Are you taking any medication?", "expected_context": "yes/no or named medication(s)"},
    {"sequence": 8, "type": "question", "text": "Have you had any recent symptoms?", "expected_context": "yes/no or described symptoms"},
    {"sequence": 9, "type": "question", "text": "When was your last medical checkup?", "expected_context": "a date or time period"},
    {"sequence": 10, "type": "question", "text": "How many hours do you sleep?", "expected_context": "a number of hours"},
    {"sequence": 11, "type": "question", "text": "Do you wake up feeling rested?", "expected_context": "yes/no"},
    {"sequence": 12, "type": "question", "text": "Do you use screens before bed?", "expected_context": "yes/no"},
    {"sequence": 13, "type": "question", "text": "Do you have trouble falling asleep?", "expected_context": "yes/no"},
    {"sequence": 14, "type": "question", "text": "Do you take naps?", "expected_context": "yes/no or a frequency"},
    {"sequence": 15, "type": "question", "text": "Do you exercise regularly?", "expected_context": "yes/no or a frequency"},
    {"sequence": 16, "type": "question", "text": "What type of exercise do you do?", "expected_context": "a named type of exercise"},
    {"sequence": 17, "type": "question", "text": "How many days a week do you work out?", "expected_context": "a number of days"},
    {"sequence": 18, "type": "question", "text": "What is your fitness goal?", "expected_context": "a stated fitness goal"},
    {"sequence": 19, "type": "question", "text": "What's stopping you from reaching it?", "expected_context": "an obstacle or barrier"},
    {"sequence": 20, "type": "question", "text": "How many meals do you eat daily?", "expected_context": "a number of meals"},
    {"sequence": 21, "type": "question", "text": "How much water do you drink?", "expected_context": "an amount of water"},
    {"sequence": 22, "type": "question", "text": "How often do you eat fast food?", "expected_context": "a frequency"},
    {"sequence": 23, "type": "question", "text": "Tea or coffee?", "expected_context": "a stated preference between tea and coffee"},
    {"sequence": 24, "type": "question", "text": "Do you consume sugary drinks?", "expected_context": "yes/no or a frequency"},
    {"sequence": 25, "type": "question", "text": "How stressed are you lately?", "expected_context": "a stress level description"},
    {"sequence": 26, "type": "question", "text": "What helps you relax?", "expected_context": "a relaxation activity"},
    {"sequence": 27, "type": "question", "text": "Do you spend enough time outdoors?", "expected_context": "yes/no with optional detail"},
    {"sequence": 28, "type": "question", "text": "How much time do you spend sitting?", "expected_context": "a duration"},
    {"sequence": 29, "type": "question", "text": "Do you have a healthy work-life balance?", "expected_context": "yes/no with optional reasoning"},
    {"sequence": 30, "type": "question", "text": "What's one thing you'd like to improve about your health?", "expected_context": "a named health improvement area"},
    {"sequence": 31, "type": "question", "text": "What healthy habit are you proud of?", "expected_context": "a named healthy habit"},
    {"sequence": 32, "type": "question", "text": "What's the biggest challenge in maintaining your health?", "expected_context": "a described challenge"},
    {"sequence": 33, "type": "question", "text": "What would an ideal day look like for you?", "expected_context": "a description of an ideal day"},
    {"sequence": 34, "type": "question", "text": "Is there anything health-related you'd like help with?", "expected_context": "yes/no or a request for help"}
  ]
}
```

`app/conversation_definitions/travel_planner.json`:
```json
{
  "intro_line": "Let's plan your next adventure.",
  "questions": [
    {"sequence": 0, "type": "question", "text": "What should I call you?", "expected_context": "a name or preferred nickname"},
    {"sequence": 1, "type": "question", "text": "Have you traveled recently?", "expected_context": "yes/no or a recent destination"},
    {"sequence": 2, "type": "question", "text": "What's your favorite destination so far?", "expected_context": "a destination name"},
    {"sequence": 3, "type": "question", "text": "Do you prefer domestic or international travel?", "expected_context": "a stated preference"},
    {"sequence": 4, "type": "question", "text": "Mountains, beaches, or cities?", "expected_context": "a stated preference among mountains, beaches, or cities"},
    {"sequence": 5, "type": "question", "text": "Where would you like to go next?", "expected_context": "a destination name"},
    {"sequence": 6, "type": "question", "text": "Why that destination?", "expected_context": "a reason"},
    {"sequence": 7, "type": "question", "text": "When are you planning to travel?", "expected_context": "a date, month, or season"},
    {"sequence": 8, "type": "question", "text": "How long will the trip be?", "expected_context": "a duration"},
    {"sequence": 9, "type": "question", "text": "What's your budget?", "expected_context": "a budget amount or range"},
    {"sequence": 10, "type": "question", "text": "Do you prefer luxury or budget travel?", "expected_context": "a stated preference"},
    {"sequence": 11, "type": "question", "text": "Solo, family, or friends?", "expected_context": "a stated travel-companion preference"},
    {"sequence": 12, "type": "question", "text": "Hotel, hostel, or Airbnb?", "expected_context": "a stated accommodation preference"},
    {"sequence": 13, "type": "question", "text": "Window seat or aisle seat?", "expected_context": "a stated seat preference"},
    {"sequence": 14, "type": "question", "text": "Early morning or late-night flights?", "expected_context": "a stated flight-time preference"},
    {"sequence": 15, "type": "question", "text": "Do you enjoy food tourism?", "expected_context": "yes/no"},
    {"sequence": 16, "type": "question", "text": "Adventure activities?", "expected_context": "yes/no or a named activity"},
    {"sequence": 17, "type": "question", "text": "Historical sites?", "expected_context": "yes/no"},
    {"sequence": 18, "type": "question", "text": "Shopping?", "expected_context": "yes/no"},
    {"sequence": 19, "type": "question", "text": "Nature?", "expected_context": "yes/no"},
    {"sequence": 20, "type": "question", "text": "What's the best trip you've ever had?", "expected_context": "a described trip"},
    {"sequence": 21, "type": "question", "text": "What's the worst travel experience you've had?", "expected_context": "a described experience"},
    {"sequence": 22, "type": "question", "text": "Have you ever missed a flight?", "expected_context": "yes/no with optional detail"},
    {"sequence": 23, "type": "question", "text": "Have you ever traveled alone?", "expected_context": "yes/no with optional detail"},
    {"sequence": 24, "type": "question", "text": "What's one country you'd love to visit?", "expected_context": "a country name"},
    {"sequence": 25, "type": "question", "text": "What are your must-have items when traveling?", "expected_context": "one or more named items"},
    {"sequence": 26, "type": "question", "text": "Do you overpack or travel light?", "expected_context": "a stated packing style"},
    {"sequence": 27, "type": "question", "text": "What's your ideal vacation?", "expected_context": "a description of an ideal vacation"},
    {"sequence": 28, "type": "question", "text": "How do you usually plan trips?", "expected_context": "a description of a planning approach"},
    {"sequence": 29, "type": "question", "text": "What's the first thing you do after arriving somewhere new?", "expected_context": "a described first activity"},
    {"sequence": 30, "type": "question", "text": "If you could travel anywhere tomorrow, where would you go?", "expected_context": "a destination name"},
    {"sequence": 31, "type": "question", "text": "What's on your travel bucket list?", "expected_context": "one or more destinations or experiences"},
    {"sequence": 32, "type": "question", "text": "What's one place you never want to visit?", "expected_context": "a place name"},
    {"sequence": 33, "type": "question", "text": "What would make a trip unforgettable?", "expected_context": "a described quality or experience"},
    {"sequence": 34, "type": "question", "text": "Would you like me to help plan your next journey?", "expected_context": "yes/no"}
  ]
}
```

### Step F.2 — Domain Entities & Interfaces

`app/modules/conversation/domain/entities/response_record_entity.py`:
```python
from dataclasses import dataclass


@dataclass
class ResponseRecord:
    sequence: int
    session_id: str
    user_response: str
    validation_result: str
```

`app/modules/conversation/domain/interfaces/conversation_repository_interface.py`:
```python
from abc import ABC, abstractmethod


class ConversationRepositoryInterface(ABC):

    @abstractmethod
    def load_definition(self, conversation_type: str) -> dict:
        """Loads and returns the raw JSON definition for the given conversation type."""
        raise NotImplementedError
```

`app/modules/conversation/domain/interfaces/response_repository_interface.py`:
```python
from abc import ABC, abstractmethod


class ResponseRepositoryInterface(ABC):

    @abstractmethod
    def add(self, sequence: int, session_id: str, user_response: str, validation_result: str) -> None:
        raise NotImplementedError
```

`app/modules/conversation/domain/interfaces/validation_provider_interface.py`:
```python
from abc import ABC, abstractmethod


class ValidationProviderInterface(ABC):

    @abstractmethod
    async def validate(self, item_type: str, expected_context: str, user_response: str) -> dict:
        """Validates a user response. Returns dict with 'valid' (bool) and 'reason' (str)."""
        raise NotImplementedError
```

### Step F.3 — Infrastructure Adapters

`app/modules/conversation/infrastructure/external/json_conversation_repository.py`:
```python
import json
import os
from app.modules.conversation.domain.interfaces.conversation_repository_interface import ConversationRepositoryInterface
from app.shared.exceptions.domain_exceptions import ConversationTypeNotFoundError


class JsonConversationRepository(ConversationRepositoryInterface):

    def __init__(self, definitions_dir: str = None):
        if definitions_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            definitions_dir = os.path.join(base_dir, "conversation_definitions")
        self._definitions_dir = definitions_dir

    def load_definition(self, conversation_type: str) -> dict:
        # Map conversation_type to filename (e.g. daily_life_companion -> daily_life.json)
        type_mapping = {
            "daily_life_companion": "daily_life.json",
            "career_life_advisor": "career_life.json",
            "health_wellness_assistant": "health_wellness.json",
            "travel_planner": "travel_planner.json",
        }
        filename = type_mapping.get(conversation_type, f"{conversation_type}.json")
        filepath = os.path.join(self._definitions_dir, filename)

        if not os.path.exists(filepath):
            raise ConversationTypeNotFoundError(f"Definition file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
```

`app/modules/conversation/infrastructure/external/litellm_validation_adapter.py`:
```python
import json
import litellm
from app.shared.config.settings import settings
from app.modules.conversation.domain.interfaces.validation_provider_interface import ValidationProviderInterface

VALIDATION_PROMPT = """You validate one turn of a scripted voice conversation.
Item type: {item_type}
Expected context: {expected_context}
User response: {user_response}

If item_type is "instruction", determine ONLY whether the user expressed completion
intent (e.g. done, finished, yes, ready). Do not judge whether the action occurred.
If item_type is "question", determine ONLY whether the response is topically relevant
to the expected context. Do not judge factual correctness.

Respond with strict JSON only: {{"valid": true|false, "reason": "<short reason>"}}"""


class LiteLLMValidationAdapter(ValidationProviderInterface):

    async def validate(self, item_type: str, expected_context: str, user_response: str) -> dict:
        prompt = VALIDATION_PROMPT.format(
            item_type=item_type, expected_context=expected_context, user_response=user_response
        )
        try:
            response = await litellm.acompletion(
                model=settings.ai_validation_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
            )
            text = response.choices[0].message.content
            return json.loads(text)
        except Exception:
            return {"valid": False, "reason": "validation_unavailable"}
```

`app/modules/conversation/infrastructure/persistence/sqlite_response_repository.py`:
```python
from app.shared.database.db import get_connection
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface


class SqliteResponseRepository(ResponseRepositoryInterface):

    def add(self, sequence: int, session_id: str, user_response: str, validation_result: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO responses (sequence, session_id, user_response, validation_result) VALUES (?, ?, ?, ?)",
                (sequence, session_id, user_response, validation_result),
            )
```

### Step F.4 — Conversation Engine Service

Create `app/modules/conversation/application/services/conversation_engine.py`:

```python
from app.modules.conversation.domain.interfaces.conversation_repository_interface import ConversationRepositoryInterface


class ConversationEngine:

    def __init__(self, conversation_repository: ConversationRepositoryInterface):
        self._conversation_repository = conversation_repository

    def load_script(self, conversation_type: str) -> dict:
        """Loads definition from JSON repository. Contains ZERO conversation data or DB logic."""
        return self._conversation_repository.load_definition(conversation_type)

    def get_intro_line(self, conversation_type: str) -> str:
        definition = self._conversation_repository.load_definition(conversation_type)
        return definition.get("intro_line", "Welcome to the conversation.")

    def get_current(self, conversation_type: str, index: int) -> dict | None:
        definition = self._conversation_repository.load_definition(conversation_type)
        questions = definition.get("questions", [])
        return questions[index] if index < len(questions) else None

    def is_complete(self, conversation_type: str, index: int) -> bool:
        definition = self._conversation_repository.load_definition(conversation_type)
        questions = definition.get("questions", [])
        return index >= len(questions)
```

### Step F.5 — Conversation Use Cases

`app/modules/conversation/application/use_cases/load_script.py`:
```python
from app.modules.conversation.application.services.conversation_engine import ConversationEngine


class LoadScript:

    def __init__(self, conversation_engine: ConversationEngine):
        self._conversation_engine = conversation_engine

    def execute(self, conversation_type: str) -> dict:
        return self._conversation_engine.load_script(conversation_type)
```

`app/modules/conversation/application/use_cases/get_current_question.py`:
```python
from app.modules.conversation.application.services.conversation_engine import ConversationEngine


class GetCurrentQuestion:

    def __init__(self, conversation_engine: ConversationEngine):
        self._conversation_engine = conversation_engine

    def execute(self, conversation_type: str, index: int) -> dict | None:
        return self._conversation_engine.get_current(conversation_type, index)
```

`app/modules/conversation/application/use_cases/check_completion.py`:
```python
from app.modules.conversation.application.services.conversation_engine import ConversationEngine


class CheckCompletion:

    def __init__(self, conversation_engine: ConversationEngine):
        self._conversation_engine = conversation_engine

    def execute(self, conversation_type: str, index: int) -> bool:
        return self._conversation_engine.is_complete(conversation_type, index)
```

`app/modules/conversation/application/use_cases/validate_response.py`:
```python
from app.modules.conversation.domain.interfaces.validation_provider_interface import ValidationProviderInterface


class ValidateResponse:

    def __init__(self, validation_provider: ValidationProviderInterface):
        self._validation_provider = validation_provider

    async def execute(self, item_type: str, expected_context: str, user_response: str) -> dict:
        return await self._validation_provider.validate(item_type, expected_context, user_response)
```

`app/modules/conversation/application/use_cases/record_response.py`:
```python
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface


class RecordResponse:

    def __init__(self, response_repository: ResponseRepositoryInterface):
        self._response_repository = response_repository

    def execute(self, sequence: int, session_id: str, user_response: str, validation_result: str) -> None:
        self._response_repository.add(sequence, session_id, user_response, validation_result)
```

---

<a id="phase-g"></a>
## Phase G: Voice Module (Deepgram Streaming STT & TTS)

### Step G.1 — Domain Interfaces

`app/modules/voice/domain/interfaces/stt_provider_interface.py`:
```python
from abc import ABC, abstractmethod


class STTProviderInterface(ABC):

    @abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_audio(self, chunk: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    async def receive_any(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def receive_transcript(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
```

`app/modules/voice/domain/interfaces/tts_provider_interface.py`:
```python
from abc import ABC, abstractmethod


class TTSProviderInterface(ABC):

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError
```

### Step G.2 — Infrastructure Adapters

`app/modules/voice/infrastructure/external/deepgram_stt_adapter.py`:
```python
import json
import websockets
from app.shared.config.settings import settings
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface

DEEPGRAM_STT_URL = "wss://api.deepgram.com/v1/listen?punctuate=true&interim_results=true"


class DeepgramSTTAdapter(STTProviderInterface):

    def __init__(self):
        self._ws = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            DEEPGRAM_STT_URL,
            extra_headers={"Authorization": f"Token {settings.deepgram_api_key}"},
        )

    async def send_audio(self, chunk: bytes) -> None:
        if self._ws:
            await self._ws.send(chunk)

    async def receive_any(self) -> dict:
        message = await self._ws.recv()
        return json.loads(message)

    async def receive_transcript(self) -> str | None:
        data = await self.receive_any()
        alt = data.get("channel", {}).get("alternatives", [{}])[0]
        transcript = alt.get("transcript", "")
        return transcript if data.get("is_final") and transcript else None

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
```

`app/modules/voice/infrastructure/external/deepgram_tts_adapter.py`:
```python
import httpx
from app.shared.config.settings import settings
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface

DEEPGRAM_TTS_URL = "https://api.deepgram.com/v1/speak?model=aura-asteria-en"


class DeepgramTTSAdapter(TTSProviderInterface):

    async def synthesize(self, text: str) -> bytes:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                DEEPGRAM_TTS_URL,
                headers={
                    "Authorization": f"Token {settings.deepgram_api_key}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
            )
            resp.raise_for_status()
            return resp.content
```

### Step G.3 — Application Use Cases

`app/modules/voice/application/use_cases/synthesize_speech.py`:
```python
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface


class SynthesizeSpeech:

    def __init__(self, tts_provider: TTSProviderInterface):
        self._tts_provider = tts_provider

    async def execute(self, text: str) -> bytes:
        return await self._tts_provider.synthesize(text)
```

`app/modules/voice/application/use_cases/stream_speech_to_text.py`:
```python
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface


class StreamSpeechToText:

    def __init__(self, stt_provider: STTProviderInterface):
        self._stt_provider = stt_provider

    async def connect(self) -> None:
        await self._stt_provider.connect()

    async def send_audio(self, chunk: bytes) -> None:
        await self._stt_provider.send_audio(chunk)

    async def receive_any(self) -> dict:
        return await self._stt_provider.receive_any()

    async def receive_transcript(self) -> str | None:
        return await self._stt_provider.receive_transcript()

    async def close(self) -> None:
        await self._stt_provider.close()
```

---

<a id="phase-h"></a>
## Phase H: Interruption Module

### Step H.1 — Domain Entity: `app/modules/interruption/domain/entities/interruption_entity.py`

```python
from dataclasses import dataclass


@dataclass
class Interruption:
    session_id: str
    interruption_type: str  # 'stop' | 'cancel' | 'repeat' | 'correction'
    interruption_text: str
    timestamp: str
```

### Step H.2 — Interface: `app/modules/interruption/domain/interfaces/interruption_repository_interface.py`

```python
from abc import ABC, abstractmethod


class InterruptionRepositoryInterface(ABC):

    @abstractmethod
    def add(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        raise NotImplementedError
```

### Step H.3 — Adapter: `app/modules/interruption/infrastructure/persistence/sqlite_interruption_repository.py`

```python
from datetime import datetime, timezone
from app.shared.database.db import get_connection
from app.modules.interruption.domain.interfaces.interruption_repository_interface import InterruptionRepositoryInterface


class SqliteInterruptionRepository(InterruptionRepositoryInterface):

    def add(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO interruptions (session_id, interruption_type, interruption_text, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, interruption_type, interruption_text, datetime.now(timezone.utc).isoformat()),
            )
```

### Step H.4 — Use Cases

`app/modules/interruption/application/use_cases/classify_interruption.py`:
```python
STOP_PATTERNS = {"stop", "wait", "hold on"}
CANCEL_PATTERNS = {"cancel", "end session", "quit"}
REPEAT_PATTERNS = {"repeat", "say that again", "come again"}
CORRECTION_MARKERS = {"no,", "actually,", "i meant", "correction"}


class ClassifyInterruption:

    def execute(self, transcript: str) -> str | None:
        t = transcript.strip().lower()
        if t in STOP_PATTERNS:
            return "stop"
        if t in CANCEL_PATTERNS:
            return "cancel"
        if t in REPEAT_PATTERNS:
            return "repeat"
        if any(t.startswith(marker) for marker in CORRECTION_MARKERS):
            return "correction"
        return None
```

`app/modules/interruption/application/use_cases/record_interruption.py`:
```python
from app.modules.interruption.domain.interfaces.interruption_repository_interface import InterruptionRepositoryInterface


class RecordInterruption:

    def __init__(self, interruption_repository: InterruptionRepositoryInterface):
        self._interruption_repository = interruption_repository

    def execute(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        self._interruption_repository.add(session_id, interruption_type, interruption_text)
```

---

<a id="phase-i"></a>
## Phase I: Presentation Entrypoints & WebSocket Handler

### Step I.1 — `app/entrypoints/websocket/connection_manager.py`

```python
from fastapi import WebSocket


class ConnectionManager:

    def __init__(self):
        self.active: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.active[session_id] = ws

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)

    async def send_json(self, session_id: str, payload: dict):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_json(payload)

    async def send_bytes(self, session_id: str, data: bytes):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_bytes(data)


manager = ConnectionManager()
```

### Step I.2 — `app/entrypoints/response_formatter.py`

```python
def event(event_name: str, payload: dict | None = None) -> dict:
    return {"event": event_name, "payload": payload or {}}


def question_event(item: dict) -> dict:
    return event("question" if item["type"] == "question" else "instruction", {
        "text": item["text"], "sequence": item["sequence"],
    })


def validation_event(valid: bool, reason: str) -> dict:
    return event("validation_result", {"valid": valid, "reason": reason})


def completed_event() -> dict:
    return event("session_completed")


def cancelled_event() -> dict:
    return event("session_cancelled")


def error_event(message: str) -> dict:
    return event("error", {"message": message})
```

### Step I.3 — `app/entrypoints/http/health.py`

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}
```

### Step I.4 — `app/entrypoints/websocket/conversation_handler.py` (Synchronized Handler)

```python
import uuid
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.entrypoints.websocket.connection_manager import manager
from app.entrypoints import response_formatter as fmt
from app.shared.config.settings import settings

# Infrastructure adapters
from app.modules.session.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository
from app.modules.message.infrastructure.persistence.sqlite_message_repository import SqliteMessageRepository
from app.modules.conversation.infrastructure.external.json_conversation_repository import JsonConversationRepository
from app.modules.conversation.infrastructure.persistence.sqlite_response_repository import SqliteResponseRepository
from app.modules.conversation.infrastructure.external.litellm_validation_adapter import LiteLLMValidationAdapter
from app.modules.interruption.infrastructure.persistence.sqlite_interruption_repository import SqliteInterruptionRepository
from app.modules.voice.infrastructure.external.deepgram_stt_adapter import DeepgramSTTAdapter
from app.modules.voice.infrastructure.external.deepgram_tts_adapter import DeepgramTTSAdapter

# Application use cases
from app.modules.session.application.use_cases.create_session import CreateSession
from app.modules.session.application.use_cases.get_session import GetSession
from app.modules.session.application.use_cases.update_pointer import UpdatePointer
from app.modules.session.application.use_cases.pause_session import PauseSession
from app.modules.session.application.use_cases.close_session import CloseSession
from app.modules.message.application.use_cases.add_message import AddMessage
from app.modules.message.application.use_cases.get_messages import GetMessages
from app.modules.conversation.application.services.conversation_engine import ConversationEngine
from app.modules.conversation.application.use_cases.validate_response import ValidateResponse
from app.modules.conversation.application.use_cases.record_response import RecordResponse
from app.modules.interruption.application.use_cases.classify_interruption import ClassifyInterruption
from app.modules.interruption.application.use_cases.record_interruption import RecordInterruption
from app.modules.voice.application.use_cases.synthesize_speech import SynthesizeSpeech

router = APIRouter()


@router.websocket("/ws/{conversation_type}")
async def conversation_socket(
    ws: WebSocket,
    conversation_type: str,
    session_id: Optional[str] = None
):
    # --- Dependency Injection ---
    session_repo = SqliteSessionRepository()
    message_repo = SqliteMessageRepository()
    conversation_repo = JsonConversationRepository()
    response_repo = SqliteResponseRepository()
    interruption_repo = SqliteInterruptionRepository()
    tts_adapter = DeepgramTTSAdapter()
    stt_adapter = DeepgramSTTAdapter()
    validation_adapter = LiteLLMValidationAdapter()

    create_session = CreateSession(session_repo)
    get_session = GetSession(session_repo)
    update_pointer = UpdatePointer(session_repo)
    pause_session = PauseSession(session_repo)
    close_session = CloseSession(session_repo)
    add_message = AddMessage(message_repo)
    get_messages = GetMessages(message_repo)
    conversation_engine = ConversationEngine(conversation_repo)
    validate_response = ValidateResponse(validation_adapter)
    record_response = RecordResponse(response_repo)
    classify_interruption = ClassifyInterruption()
    record_interruption = RecordInterruption(interruption_repo)
    synthesize_speech = SynthesizeSpeech(tts_adapter)

    # --- Backend Session ID Ownership & Recovery ---
    is_recovery = False
    if session_id:
        existing = get_session.execute(session_id)
        if existing and existing["status"] in ("active", "paused"):
            is_recovery = True
        else:
            session_id = str(uuid.uuid4())
    else:
        session_id = str(uuid.uuid4())

    await manager.connect(session_id, ws)

    if not is_recovery:
        create_session.execute(session_id, conversation_type)
        index, retries = 0, 0
    else:
        session_data = get_session.execute(session_id)
        index = session_data["current_question_index"]
        retries = session_data["retries"]
        update_pointer.execute(session_id, index, "asking", retries)

    await stt_adapter.connect()

    async def speak(text: str):
        add_message.execute(session_id, "system", text)
        audio = await synthesize_speech.execute(text)
        await manager.send_json(session_id, fmt.event("tts_audio_meta", {"text": text}))
        await manager.send_bytes(session_id, audio)

    async def ask_current():
        nonlocal index
        item = conversation_engine.get_current(conversation_type, index)
        if item is None:
            close_session.execute(session_id, "completed")
            await manager.send_json(session_id, fmt.completed_event())
            await ws.close()
            return False
        await manager.send_json(session_id, fmt.question_event(item))
        await speak(item["text"])
        return True

    # --- Session Started Event ---
    await manager.send_json(session_id, fmt.event("session_started", {
        "session_id": session_id,
        "is_recovery": is_recovery
    }))

    # --- Transcript Recovery on Reconnect ---
    if is_recovery:
        past_messages = get_messages.execute(session_id)
        await manager.send_json(session_id, fmt.event("transcript_recovery", {
            "messages": past_messages
        }))
        await ask_current()
    else:
        await speak(conversation_engine.get_intro_line(conversation_type))
        if not await ask_current():
            return

    # --- Main Event Loop ---
    try:
        while True:
            frame = await ws.receive()
            if "bytes" in frame and frame["bytes"] is not None:
                await stt_adapter.send_audio(frame["bytes"])

                raw = await stt_adapter.receive_any()
                alt = raw.get("channel", {}).get("alternatives", [{}])[0]
                text = alt.get("transcript", "")
                is_final = raw.get("is_final", False)

                if text and not is_final:
                    await manager.send_json(
                        session_id, fmt.event("user_partial_transcript", {"text": text})
                    )
                    continue

                if not is_final or not text:
                    continue

                transcript = text
            else:
                continue

            add_message.execute(session_id, "user", transcript)

            interruption = classify_interruption.execute(transcript)
            if interruption == "stop":
                record_interruption.execute(session_id, "stop", transcript)
                await manager.send_json(session_id, fmt.event("tts_stop"))
                continue
            if interruption == "cancel":
                record_interruption.execute(session_id, "cancel", transcript)
                close_session.execute(session_id, "cancelled")
                await manager.send_json(session_id, fmt.cancelled_event())
                await ws.close()
                break
            if interruption == "repeat":
                record_interruption.execute(session_id, "repeat", transcript)
                await ask_current()
                continue
            if interruption == "correction":
                record_interruption.execute(session_id, "correction", transcript)

            item = conversation_engine.get_current(conversation_type, index)
            result = await validate_response.execute(item["type"], item["expected_context"], transcript)
            record_response.execute(
                item["sequence"], session_id, transcript, "valid" if result["valid"] else "invalid"
            )
            await manager.send_json(session_id, fmt.validation_event(result["valid"], result["reason"]))

            if result["valid"]:
                index += 1
                retries = 0
                update_pointer.execute(session_id, index, "asking", retries)
                if not await ask_current():
                    break
            else:
                retries += 1
                update_pointer.execute(session_id, index, "repeating", retries)
                if retries >= settings.max_retries_per_item:
                    await speak("Let's move on for now.")
                    index += 1
                    retries = 0
                    update_pointer.execute(session_id, index, "asking", retries)
                    if not await ask_current():
                        break
                else:
                    await speak(result["reason"])
                    await ask_current()

    except WebSocketDisconnect:
        pause_session.execute(session_id)
    finally:
        await stt_adapter.close()
        manager.disconnect(session_id)
```

---

<a id="phase-j"></a>
## Phase J: Application Assembly (`main.py`)

### Step J.1 — Constants

`app/shared/constants/conversation_types.py`:
```python
CONVERSATION_TYPES = [
    "daily_life_companion",
    "career_life_advisor",
    "health_wellness_assistant",
    "travel_planner",
]
```

`app/shared/constants/states.py`:
```python
STATES = ["welcoming", "asking", "listening", "validating", "speaking", "repeating", "paused", "completed"]
```

`app/shared/constants/interruption_types.py`:
```python
INTERRUPTION_TYPES = ["stop", "cancel", "repeat", "correction"]
```

### Step J.2 — Logger, Exceptions, Schemas

`app/shared/logging/logger.py`:
```python
import logging
logger = logging.getLogger("conversation_widget")
logging.basicConfig(level=logging.INFO)
```

`app/shared/exceptions/domain_exceptions.py`:
```python
class ConversationTypeNotFoundError(Exception): pass
class SessionNotFoundError(Exception): pass
```

`app/shared/schemas/session_schema.py`:
```python
from pydantic import BaseModel


class SessionState(BaseModel):
    session_id: str
    conversation_type: str
    status: str
    current_question_index: int
    current_state: str
    retries: int
```

`app/shared/schemas/message_schema.py`:
```python
from pydantic import BaseModel


class MessageIn(BaseModel):
    session_id: str
    sender: str
    text: str
```

`app/shared/schemas/ws_schema.py`:
```python
from pydantic import BaseModel
from typing import Optional, Literal


class WSEvent(BaseModel):
    event: Literal[
        "session_started", "transcript_recovery", "question", "instruction",
        "validation_result", "tts_audio_meta", "tts_stop",
        "user_partial_transcript", "session_completed", "session_cancelled", "error"
    ]
    payload: Optional[dict] = None
```

### Step J.3 — `main.py`

Create `backend/main.py`:

```python
from fastapi import FastAPI
from app.entrypoints.websocket.conversation_handler import router as ws_router
from app.entrypoints.http.health import router as health_router
from app.shared.database.init_db import init_db

app = FastAPI(title="Conversational Widget Platform Backend")


@app.on_event("startup")
async def on_startup():
    init_db()


app.include_router(health_router)
app.include_router(ws_router)
```

---

<a id="phase-k"></a>
## Phase K: Backend Test Suite

### Step K.1 — `tests/shared/test_migrations.py`

```python
import sqlite3
import pytest
from app.shared.config.settings import settings


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "database_path", db_path)
    yield db_path


def test_migrations_run(fresh_db):
    from app.shared.database.init_db import init_db
    init_db()
    conn = sqlite3.connect(fresh_db)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert {"sessions", "messages", "responses", "interruptions"}.issubset(tables)
```

### Step K.2 — `tests/modules/session/test_session_use_cases.py`

```python
import pytest
from app.shared.config.settings import settings


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "database_path", db_path)
    from app.shared.database.init_db import init_db
    init_db()
    yield


def test_session_lifecycle():
    from app.modules.session.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository
    from app.modules.session.application.use_cases.create_session import CreateSession
    from app.modules.session.application.use_cases.get_session import GetSession
    from app.modules.session.application.use_cases.pause_session import PauseSession
    from app.modules.session.application.use_cases.close_session import CloseSession

    repo = SqliteSessionRepository()
    create = CreateSession(repo)
    get = GetSession(repo)
    pause = PauseSession(repo)
    close = CloseSession(repo)

    create.execute("s-123", "daily_life_companion")
    s = get.execute("s-123")
    assert s["status"] == "active"

    pause.execute("s-123")
    s = get.execute("s-123")
    assert s["status"] == "paused"

    close.execute("s-123", "completed")
    s = get.execute("s-123")
    assert s["status"] == "completed"
```

### Step K.3 — `tests/modules/conversation/test_conversation_engine.py`

```python
import pytest
from app.modules.conversation.infrastructure.external.json_conversation_repository import JsonConversationRepository
from app.modules.conversation.application.services.conversation_engine import ConversationEngine


def test_json_script_loading():
    repo = JsonConversationRepository()
    engine = ConversationEngine(repo)
    definition = engine.load_script("daily_life_companion")
    assert len(definition["questions"]) == 30
    assert engine.get_current("daily_life_companion", 0)["text"] == "What should I call you?"
```

### Step K.4 — `tests/modules/interruption/test_classify_interruption.py`

```python
from app.modules.interruption.application.use_cases.classify_interruption import ClassifyInterruption


def test_stop():
    c = ClassifyInterruption()
    assert c.execute("stop") == "stop"
    assert c.execute("wait") == "stop"


def test_cancel():
    c = ClassifyInterruption()
    assert c.execute("cancel") == "cancel"


def test_repeat():
    c = ClassifyInterruption()
    assert c.execute("repeat") == "repeat"


def test_correction():
    c = ClassifyInterruption()
    assert c.execute("no, apple") == "correction"
```

### Step K.5 — `tests/integration/test_websocket_flow.py`

```python
import asyncio
import json
import pytest
import websockets


@pytest.mark.asyncio
async def test_session_started_event():
    url = "ws://localhost:8000/ws/daily_life_companion"
    async with websockets.connect(url) as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(msg)
        assert data["event"] == "session_started"
        assert "session_id" in data["payload"]
```

---

<a id="phase-l"></a>
## Phase L: React Frontend Application

Navigate to `frontend/`:

```bash
cd ../frontend
npm init vite@latest ./ -- --template react
npm install
```

### Step L.1 — `frontend/package.json`

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

### Step L.2 — `frontend/vite.config.js`

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

### Step L.3 — `frontend/index.html`

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

### Step L.4 — `frontend/.env.example`

```env
VITE_WS_BASE_URL=ws://localhost:8000
```

Create `.env`:
```bash
cp .env.example .env
```

### Step L.5 — `frontend/.gitignore`

```text
node_modules/
dist/
.env
```

### Step L.6 — `frontend/src/main.jsx`

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

### Step L.7 — Context Reducer: `src/context/ConversationContext.jsx`

```jsx
import { createContext, useReducer } from "react";

const initialState = {
  isOpen: false,
  sessionId: null,
  status: "idle", // idle | connecting | active | paused | completed | cancelled
  transcriptLines: [], // { id, speaker, text, isHighlighted }
  partialTranscript: "",
  isSpeaking: false,
  isListening: false,
};

function reducer(state, action) {
  switch (action.type) {
    case "OPEN_WIDGET":
      return { ...state, isOpen: true };
    case "CLOSE_WIDGET":
      return { ...state, isOpen: false };
    case "SESSION_STARTED":
      return { ...state, status: "active", sessionId: action.sessionId };
    case "RECOVER_TRANSCRIPT":
      return {
        ...state,
        transcriptLines: action.messages.map((m, i) => ({
          id: i,
          speaker: m.sender === "system" ? "assistant" : "user",
          text: m.text,
          isHighlighted: false,
        })),
      };
    case "APPEND_TRANSCRIPT_LINE":
      return {
        ...state,
        transcriptLines: [...state.transcriptLines.slice(-5), action.line],
      };
    case "SET_PARTIAL_TRANSCRIPT":
      return { ...state, partialTranscript: action.text };
    case "CLEAR_PARTIAL_TRANSCRIPT":
      return { ...state, partialTranscript: "" };
    case "SET_ASSISTANT_HIGHLIGHT":
      return { ...state, isSpeaking: action.value };
    case "SET_LISTENING":
      return { ...state, isListening: action.value };
    case "SESSION_COMPLETED":
      return { ...state, status: "completed", isSpeaking: false, isListening: false };
    case "SESSION_CANCELLED":
      return { ...state, status: "cancelled", isSpeaking: false, isListening: false };
    case "RESET_FOR_NEW_SESSION":
      return { ...initialState, isOpen: true };
    default:
      return state;
  }
}

export const ConversationContext = createContext(null);

export function ConversationProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <ConversationContext.Provider value={{ state, dispatch }}>
      {children}
    </ConversationContext.Provider>
  );
}
```

### Step L.8 — Audio Utils: `src/utils/audioUtils.js`

```javascript
export function createMicStream(onChunk) {
  return navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
    const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) e.data.arrayBuffer().then(onChunk);
    };
    recorder.start(250);
    return { recorder, stream };
  });
}

export function stopMicStream({ recorder, stream }) {
  recorder.stop();
  stream.getTracks().forEach((t) => t.stop());
}

export function playAudioBuffer(arrayBuffer, audioContext) {
  return audioContext.decodeAudioData(arrayBuffer.slice(0)).then((decoded) => {
    const source = audioContext.createBufferSource();
    source.buffer = decoded;
    source.connect(audioContext.destination);
    source.start(0);
    return source;
  });
}
```

### Step L.9 — WebSocket Service: `src/services/websocketService.js`

```javascript
export function createConversationSocket({ conversationType, sessionId, onEvent, onAudio }) {
  let url = `${import.meta.env.VITE_WS_BASE_URL}/ws/${conversationType}`;
  if (sessionId) {
    url += `?session_id=${sessionId}`;
  }
  const socket = new WebSocket(url);
  socket.binaryType = "arraybuffer";

  socket.onmessage = (msg) => {
    if (typeof msg.data === "string") {
      onEvent(JSON.parse(msg.data));
    } else {
      onAudio(msg.data);
    }
  };

  return {
    socket,
    sendAudioChunk: (buffer) => {
      if (socket.readyState === WebSocket.OPEN) socket.send(buffer);
    },
    close: () => socket.close(),
  };
}
```

### Step L.10 — Audio Hook: `src/hooks/useDeepgramAudio.js`

```javascript
import { useRef, useCallback } from "react";
import { createMicStream, stopMicStream, playAudioBuffer } from "../utils/audioUtils";

export function useDeepgramAudio() {
  const micRef = useRef(null);
  const audioContextRef = useRef(null);
  const currentSourceRef = useRef(null);

  const getAudioContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
    return audioContextRef.current;
  };

  const startMic = useCallback(async (onChunk) => {
    micRef.current = await createMicStream(onChunk);
  }, []);

  const stopMic = useCallback(() => {
    if (micRef.current) {
      stopMicStream(micRef.current);
      micRef.current = null;
    }
  }, []);

  const playTTS = useCallback(async (arrayBuffer) => {
    const source = await playAudioBuffer(arrayBuffer, getAudioContext());
    currentSourceRef.current = source;
    return new Promise((resolve) => {
      source.onended = resolve;
    });
  }, []);

  const stopTTS = useCallback(() => {
    if (currentSourceRef.current) {
      try {
        currentSourceRef.current.stop();
      } catch (_) {}
      currentSourceRef.current = null;
    }
  }, []);

  return { startMic, stopMic, playTTS, stopTTS };
}
```

### Step L.11 — WebSocket Hook: `src/hooks/useWebSocket.js`

```javascript
import { useRef, useContext, useCallback } from "react";
import { ConversationContext } from "../context/ConversationContext";
import { createConversationSocket } from "../services/websocketService";
import { useDeepgramAudio } from "./useDeepgramAudio";

export function useWebSocket(conversationType) {
  const { state, dispatch } = useContext(ConversationContext);
  const connRef = useRef(null);
  const { startMic, stopMic, playTTS, stopTTS } = useDeepgramAudio();

  const connect = useCallback(() => {
    const savedSessionId = sessionStorage.getItem("widget_session_id");

    const onEvent = (evt) => {
      switch (evt.event) {
        case "session_started":
          sessionStorage.setItem("widget_session_id", evt.payload.session_id);
          dispatch({ type: "SESSION_STARTED", sessionId: evt.payload.session_id });
          break;
        case "transcript_recovery":
          dispatch({ type: "RECOVER_TRANSCRIPT", messages: evt.payload.messages });
          break;
        case "user_partial_transcript":
          dispatch({ type: "SET_PARTIAL_TRANSCRIPT", text: evt.payload.text });
          break;
        case "question":
        case "instruction":
          dispatch({ type: "CLEAR_PARTIAL_TRANSCRIPT" });
          break;
        case "tts_audio_meta":
          dispatch({
            type: "APPEND_TRANSCRIPT_LINE",
            line: { id: Date.now(), speaker: "assistant", text: evt.payload.text, isHighlighted: true },
          });
          dispatch({ type: "SET_ASSISTANT_HIGHLIGHT", value: true });
          break;
        case "tts_stop":
          stopTTS();
          dispatch({ type: "SET_ASSISTANT_HIGHLIGHT", value: false });
          break;
        case "session_completed":
          stopMic();
          sessionStorage.removeItem("widget_session_id");
          dispatch({ type: "SESSION_COMPLETED" });
          break;
        case "session_cancelled":
          stopMic();
          sessionStorage.removeItem("widget_session_id");
          dispatch({ type: "SESSION_CANCELLED" });
          break;
        default:
          break;
      }
    };

    const onAudio = async (arrayBuffer) => {
      dispatch({ type: "SET_ASSISTANT_HIGHLIGHT", value: true });
      await playTTS(arrayBuffer);
      dispatch({ type: "SET_ASSISTANT_HIGHLIGHT", value: false });
      dispatch({ type: "SET_LISTENING", value: true });
    };

    connRef.current = createConversationSocket({
      conversationType,
      sessionId: savedSessionId,
      onEvent,
      onAudio,
    });

    startMic((chunk) => {
      connRef.current?.sendAudioChunk(chunk);
    });
  }, [conversationType, dispatch, playTTS, startMic, stopMic, stopTTS]);

  const disconnect = useCallback(() => {
    stopMic();
    stopTTS();
    connRef.current?.close();
  }, [stopMic, stopTTS]);

  return { connect, disconnect };
}
```

### Step L.12 — Components & Main Window Assembly

`src/components/WidgetButton.jsx`:
```jsx
import { useContext } from "react";
import { ConversationContext } from "../context/ConversationContext";

export default function WidgetButton() {
  const { dispatch } = useContext(ConversationContext);
  return (
    <button onClick={() => dispatch({ type: "OPEN_WIDGET" })} aria-label="Open assistant">
      Talk to Assistant
    </button>
  );
}
```

`src/components/SpeakingIndicator.jsx`:
```jsx
import { useContext } from "react";
import { ConversationContext } from "../context/ConversationContext";

export default function SpeakingIndicator() {
  const { state } = useContext(ConversationContext);
  if (!state.isSpeaking) return null;
  return <div className="speaking-indicator">● Assistant is speaking…</div>;
}
```

`src/components/ListeningIndicator.jsx`:
```jsx
import { useContext } from "react";
import { ConversationContext } from "../context/ConversationContext";

export default function ListeningIndicator() {
  const { state } = useContext(ConversationContext);
  if (!state.isListening) return null;
  return <div className="listening-indicator">◎ Listening…</div>;
}
```

`src/components/SessionEndedState.jsx`:
```jsx
import { useContext } from "react";
import { ConversationContext } from "../context/ConversationContext";

export default function SessionEndedState() {
  const { state, dispatch } = useContext(ConversationContext);
  if (state.status !== "completed" && state.status !== "cancelled") return null;
  return (
    <div className="session-ended">
      <p>{state.status === "completed" ? "Session complete." : "Session cancelled."}</p>
      <button onClick={() => dispatch({ type: "CLOSE_WIDGET" })}>Close</button>
    </div>
  );
}
```

`src/components/ConversationWindow.jsx` **(Live Subtitles Rendered Directly)**:
```jsx
import { useContext, useEffect, useRef } from "react";
import { ConversationContext } from "../context/ConversationContext";
import { useWebSocket } from "../hooks/useWebSocket";
import SpeakingIndicator from "./SpeakingIndicator";
import ListeningIndicator from "./ListeningIndicator";
import SessionEndedState from "./SessionEndedState";

export default function ConversationWindow({ conversationType = "daily_life_companion" }) {
  const { state } = useContext(ConversationContext);
  const { connect, disconnect } = useWebSocket(conversationType);
  const subtitlesRef = useRef(null);

  useEffect(() => {
    if (state.isOpen && state.status === "idle") connect();
    return () => {
      if (!state.isOpen) disconnect();
    };
  }, [state.isOpen, connect, disconnect, state.status]);

  useEffect(() => {
    if (subtitlesRef.current) {
      subtitlesRef.current.scrollTop = subtitlesRef.current.scrollHeight;
    }
  }, [state.transcriptLines, state.partialTranscript]);

  if (!state.isOpen) return null;

  return (
    <div className="conversation-window" style={{ border: "1px solid #ccc", padding: "16px", borderRadius: "8px", width: "320px" }}>
      <h3>AI Companion</h3>
      
      {/* Live subtitles rendered directly inside ConversationWindow (no separate transcript component) */}
      <div className="subtitles" ref={subtitlesRef} style={{ maxHeight: "180px", overflowY: "auto", margin: "12px 0" }}>
        {state.transcriptLines.map((line) => (
          <div
            key={line.id}
            className={`subtitle-line ${line.speaker}`}
            style={{
              opacity: line.isHighlighted ? 1.0 : 0.7,
              fontWeight: line.isHighlighted ? 600 : 400,
              marginBottom: "6px",
            }}
          >
            <strong>{line.speaker === "assistant" ? "Assistant" : "You"}:</strong> {line.text}
          </div>
        ))}
        {state.partialTranscript && (
          <div className="subtitle-line user partial" style={{ fontStyle: "italic", opacity: 0.5 }}>
            <strong>You:</strong> {state.partialTranscript}…
          </div>
        )}
      </div>

      <SpeakingIndicator />
      <ListeningIndicator />
      <SessionEndedState />
    </div>
  );
}
```

`src/pages/HomePage.jsx`:
```jsx
import WidgetButton from "../components/WidgetButton";
import ConversationWindow from "../components/ConversationWindow";

export default function HomePage() {
  return (
    <main style={{ padding: "32px", fontFamily: "sans-serif" }}>
      <h1>Conversational Assistant Platform</h1>
      <WidgetButton />
      <ConversationWindow conversationType="daily_life_companion" />
    </main>
  );
}
```

`src/App.jsx`:
```jsx
import { ConversationProvider } from "./context/ConversationContext";
import HomePage from "./pages/HomePage";

export default function App() {
  return (
    <ConversationProvider>
      <HomePage />
    </ConversationProvider>
  );
}
```

---

<a id="phase-m"></a>
## Phase M: End-to-End Verification

### Step M.1 — Run Backend Server

In your `backend` terminal:

```bash
uvicorn main:app --reload --port 8000
```

Verify health check:

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}
```

### Step M.2 — Run Frontend Dev Server

In your `frontend` terminal:

```bash
npm run dev
```

Open `http://localhost:3000` in your browser.

### Step M.3 — Manual Verification Protocol

1. **New Session Creation**: Click "Talk to Assistant". Verify `session_id` UUID is generated server-side and received in the `session_started` WebSocket event.
2. **Audio & Script Flow**: Hear the intro line ("I'd love to know how your day is going.") and first question from `daily_life.json`. Speak a response. Verify Deepgram STT transcribes the audio and `LiteLLMValidationAdapter` validates topical relevance.
3. **Interruption Handling**: Say "repeat". Verify the assistant replays the current question. Say "stop". Verify TTS stops immediately.
4. **PAUSED State & Reconnect**: Refresh the browser page mid-conversation. Re-open the widget. Verify the client re-sends `?session_id={id}`, backend recovers the session state from SQLite, emits `transcript_recovery`, and resumes at the saved question sequence index.
