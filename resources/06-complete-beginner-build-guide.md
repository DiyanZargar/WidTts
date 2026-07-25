# Complete Build Guide — Modular Monolith + Clean Architecture

> Every command, file path, and code block in this guide reflects the
> **Modular Monolith + Clean Architecture** structure. Follow each step
> in order. Do not skip ahead — each phase proves the previous one works
> before building on top of it.

---

## Table of Contents

- [Part A — Architecture Overview](#part-a)
- [Part B — Environment Setup](#part-b)
- [Part C — Project Skeleton](#part-c)
- [Part D — Phase 1: Database Layer (Shared)](#part-d)
- [Part E — Phase 2: Session & Message Modules (Domain + Infrastructure)](#part-e)
- [Part F — Phase 3: Conversation Module (Scripts + Engine)](#part-f)
- [Part G — Phase 4: Voice Module (Deepgram STT/TTS)](#part-g)
- [Part H — Phase 5: Interruption Module + AI Validation](#part-h)
- [Part I — Phase 6: Entrypoints (WebSocket Handler + HTTP)](#part-i)
- [Part J — Phase 7: Application Assembly](#part-j)
- [Part K — Phase 8: Backend Test Suite](#part-k)
- [Part L — Phase 9: Frontend](#part-l)
- [Part M — Phase 10: Integration Test](#part-m)

---

<a id="part-a"></a>
## Part A — Architecture Overview

### What is Modular Monolith + Clean Architecture?

**Modular Monolith** — the backend is a single deployable unit, organized
into self-contained feature modules with clear boundaries. Each module
owns its business capability and can be understood independently.

**Clean Architecture** — every module enforces strict dependency rules:
dependencies always point inward toward the Domain layer. The domain
never depends on frameworks, databases, or external services.

### Dependency Rule

```
Presentation
       ↓
Application
       ↓
  Domain

Infrastructure
       ↑
  Domain
```

Dependencies always point inward. Presentation depends on Application.
Application depends on Domain. Infrastructure implements Domain
interfaces. Domain depends on nothing.

### Layer Responsibilities

| Layer | Responsibility | Constraints |
|---|---|---|
| **Domain** | Business entities, business rules, interfaces/contracts, value objects | Must not depend on frameworks. Must not depend on infrastructure. Must remain portable and isolated. |
| **Application** | Use cases (classes with `execute()`), orchestration, business workflows | May depend on Domain. Must not directly depend on external systems. |
| **Infrastructure** | Databases, external APIs, storage, third-party integrations | Implements contracts defined by Domain. Should be replaceable with minimal impact. |
| **Presentation** | APIs, WebSockets, request/response handling, serialization | Must not contain business logic. Acts only as an entry point into the application. |

### Modules

This project has 5 domain modules:

| Module | Owns | Key Files |
|---|---|---|
| `session` | Session lifecycle management | `Session` entity, `SessionRepositoryInterface`, 4 use cases |
| `message` | Transcript message persistence | `Message` entity, `MessageRepositoryInterface`, 1 use case |
| `conversation` | Scripted conversation flow + AI validation | `Question`/`ResponseRecord` entities, 2 repository interfaces, `ConversationEngine` service, 5 use cases |
| `voice` | Deepgram STT/TTS integration | `STTProviderInterface`/`TTSProviderInterface`, Deepgram adapters, 2 use cases |
| `interruption` | Interruption detection + recording | `Interruption` entity, `InterruptionRepositoryInterface`, 2 use cases |

Plus **shared** (database, config, constants, logging, schemas, exceptions) and **entrypoints** (WebSocket handler, HTTP health).

### Development Principles

- **Composition over inheritance.** Except for ABC interfaces.
- **Interfaces over concrete implementations.** Domain defines contracts; Infrastructure implements them.
- **Explicit dependencies over hidden dependencies.** Use cases receive their dependencies through constructor injection.
- **Small modules over large modules.**
- **No business logic in presentation layers.** The conversation handler orchestrates, but never decides.

### Glossary

| Term | Meaning in this project |
|---|---|
| **Entity** | A `@dataclass` in the domain layer representing a business object |
| **Interface** | An `abc.ABC` subclass with `@abstractmethod` methods, defined in the domain layer |
| **Use Case** | A class in the application layer with an `execute()` method implementing one business operation |
| **Adapter** | A concrete class in the infrastructure layer that implements a domain interface |
| **Service** | An application-layer class that coordinates multiple use cases or encapsulates complex business logic |
| **Entrypoint** | A presentation-layer component (FastAPI handler, HTTP route) that wires adapters into use cases and invokes them |

---

<a id="part-b"></a>
## Part B — Environment Setup

### Step B.1 — Install Python and Node.js

**Python 3.11+** is required. Check:

```bash
python3 --version
```

**Node.js 18+** is required for the frontend. Check:

```bash
node --version
npm --version
```

### Step B.2 — Create the Project Root

```bash
mkdir -p widTts/backend widTts/frontend
cd widTts
```

### Step B.3 — Set Up the Backend Virtual Environment

```bash
cd backend
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows
```

### Step B.4 — Install Backend Dependencies

Create `requirements.txt`:

```
fastapi
uvicorn[standard]
pydantic-settings
python-dotenv
websockets
httpx
```

Install:

```bash
pip install -r requirements.txt
```

### Step B.5 — Create `.env`

```bash
cp .env.example .env
```

Or create `.env` manually:

```
DEEPGRAM_API_KEY=your_deepgram_api_key_here
DATABASE_PATH=app.db
AI_VALIDATION_MODEL=claude-sonnet-4-6
MAX_RETRIES_PER_ITEM=3
```

**Get a Deepgram API key** at https://console.deepgram.com — sign up,
create a project, and copy the key. Paste it into `.env`.

### Step B.6 — Create `.gitignore` (backend)

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

---

<a id="part-c"></a>
## Part C — Project Skeleton

### Step C.1 — Create All Module Directories

Run this from `backend/`:

```bash
# Shared layer
mkdir -p app/shared/database/migrations
mkdir -p app/shared/config
mkdir -p app/shared/constants
mkdir -p app/shared/logging
mkdir -p app/shared/schemas
mkdir -p app/shared/exceptions

# Session module
mkdir -p app/modules/session/domain/entities
mkdir -p app/modules/session/domain/interfaces
mkdir -p app/modules/session/application/use_cases
mkdir -p app/modules/session/infrastructure/persistence

# Message module
mkdir -p app/modules/message/domain/entities
mkdir -p app/modules/message/domain/interfaces
mkdir -p app/modules/message/application/use_cases
mkdir -p app/modules/message/infrastructure/persistence

# Conversation module
mkdir -p app/modules/conversation/domain/entities
mkdir -p app/modules/conversation/domain/interfaces
mkdir -p app/modules/conversation/application/use_cases
mkdir -p app/modules/conversation/application/services
mkdir -p app/modules/conversation/infrastructure/persistence
mkdir -p app/modules/conversation/infrastructure/external

# Voice module
mkdir -p app/modules/voice/domain/interfaces
mkdir -p app/modules/voice/application/use_cases
mkdir -p app/modules/voice/infrastructure/external

# Interruption module
mkdir -p app/modules/interruption/domain/entities
mkdir -p app/modules/interruption/domain/interfaces
mkdir -p app/modules/interruption/application/use_cases
mkdir -p app/modules/interruption/infrastructure/persistence

# Entrypoints (presentation layer)
mkdir -p app/entrypoints/websocket
mkdir -p app/entrypoints/http

# Tests
mkdir -p tests/modules/session
mkdir -p tests/modules/conversation
mkdir -p tests/modules/interruption
mkdir -p tests/shared
mkdir -p tests/integration
```

### Step C.2 — Create All `__init__.py` Files

```bash
# App root
touch app/__init__.py

# Shared
touch app/shared/__init__.py
touch app/shared/database/__init__.py
touch app/shared/database/migrations/__init__.py
touch app/shared/config/__init__.py
touch app/shared/constants/__init__.py
touch app/shared/logging/__init__.py
touch app/shared/schemas/__init__.py
touch app/shared/exceptions/__init__.py

# Modules root
touch app/modules/__init__.py

# Session
touch app/modules/session/__init__.py
touch app/modules/session/domain/__init__.py
touch app/modules/session/domain/entities/__init__.py
touch app/modules/session/domain/interfaces/__init__.py
touch app/modules/session/application/__init__.py
touch app/modules/session/application/use_cases/__init__.py
touch app/modules/session/infrastructure/__init__.py
touch app/modules/session/infrastructure/persistence/__init__.py

# Message
touch app/modules/message/__init__.py
touch app/modules/message/domain/__init__.py
touch app/modules/message/domain/entities/__init__.py
touch app/modules/message/domain/interfaces/__init__.py
touch app/modules/message/application/__init__.py
touch app/modules/message/application/use_cases/__init__.py
touch app/modules/message/infrastructure/__init__.py
touch app/modules/message/infrastructure/persistence/__init__.py

# Conversation
touch app/modules/conversation/__init__.py
touch app/modules/conversation/domain/__init__.py
touch app/modules/conversation/domain/entities/__init__.py
touch app/modules/conversation/domain/interfaces/__init__.py
touch app/modules/conversation/application/__init__.py
touch app/modules/conversation/application/use_cases/__init__.py
touch app/modules/conversation/application/services/__init__.py
touch app/modules/conversation/infrastructure/__init__.py
touch app/modules/conversation/infrastructure/persistence/__init__.py
touch app/modules/conversation/infrastructure/external/__init__.py

# Voice
touch app/modules/voice/__init__.py
touch app/modules/voice/domain/__init__.py
touch app/modules/voice/domain/interfaces/__init__.py
touch app/modules/voice/application/__init__.py
touch app/modules/voice/application/use_cases/__init__.py
touch app/modules/voice/infrastructure/__init__.py
touch app/modules/voice/infrastructure/external/__init__.py

# Interruption
touch app/modules/interruption/__init__.py
touch app/modules/interruption/domain/__init__.py
touch app/modules/interruption/domain/entities/__init__.py
touch app/modules/interruption/domain/interfaces/__init__.py
touch app/modules/interruption/application/__init__.py
touch app/modules/interruption/application/use_cases/__init__.py
touch app/modules/interruption/infrastructure/__init__.py
touch app/modules/interruption/infrastructure/persistence/__init__.py

# Entrypoints
touch app/entrypoints/__init__.py
touch app/entrypoints/websocket/__init__.py
touch app/entrypoints/http/__init__.py

# Tests
touch tests/__init__.py
touch tests/modules/__init__.py
touch tests/modules/session/__init__.py
touch tests/modules/conversation/__init__.py
touch tests/modules/interruption/__init__.py
touch tests/shared/__init__.py
touch tests/integration/__init__.py
```

### Step C.3 — Verify the Skeleton

```bash
find app -type f -name "*.py" | sort
```

You should see all `__init__.py` files listed. The directory tree should
match the structure in `01-architecture.md` §3.

### Phase 0 — Final Check

- [ ] All directories created.
- [ ] All `__init__.py` files in place.
- [ ] `requirements.txt` installed.
- [ ] `.env` has a real Deepgram API key.

---

<a id="part-d"></a>
## Part D — Phase 1: Database Layer (Shared)

**Goal of this phase:** create the shared database infrastructure — the
connection helper, settings, and migration system — that all module
infrastructure adapters will use.

### Step D.1 — Write `app/shared/config/settings.py`

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    deepgram_api_key: str
    database_path: str = "app.db"
    ai_validation_model: str = "claude-sonnet-4-6"
    max_retries_per_item: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
```

`deepgram_api_key` has no default — Pydantic will require it in `.env`,
catching the mistake of forgetting to set a key before anything fails
at runtime.

### Step D.2 — Test Settings Load

```bash
python3 -c "from app.shared.config.settings import settings; print(settings.database_path)"
```

Expected: `app.db`

### Step D.3 — Write `app/shared/database/db.py`

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

### Step D.4 — Write the 6 Migration SQL Files

Create each file in `app/shared/database/migrations/`:

**`0001_create_sessions_table.sql`:**

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

**`0002_create_messages_table.sql`:**

```sql
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    sender TEXT NOT NULL CHECK (sender IN ('system','user')),
    text TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

**`0003_create_questions_table.sql`:**

```sql
CREATE TABLE IF NOT EXISTS questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_type TEXT NOT NULL,
    question_text TEXT NOT NULL,
    expected_context TEXT NOT NULL,
    sequence INTEGER NOT NULL
);
```

**`0004_create_responses_table.sql`:**

```sql
CREATE TABLE IF NOT EXISTS responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES questions(question_id),
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    user_response TEXT NOT NULL,
    validation_result TEXT NOT NULL CHECK (validation_result IN ('valid','invalid'))
);
```

**`0005_create_interruptions_table.sql`:**

```sql
CREATE TABLE IF NOT EXISTS interruptions (
    interruption_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    interruption_type TEXT NOT NULL CHECK (interruption_type IN ('stop','cancel','repeat','correction')),
    interruption_text TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

**`0006_add_status_index_to_sessions.sql`:**

```sql
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
```

### Step D.5 — Write the Migration Runner

Create `app/shared/database/migrations/runner.py`:

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

### Step D.6 — Write `app/shared/database/init_db.py`

```python
from app.shared.database.migrations.runner import run_migrations


def init_db():
    run_migrations()
```

### Step D.7 — Run Migrations and Verify

```bash
python3 -c "from app.shared.database.init_db import init_db; init_db()"
```

Expected output — 6 lines:

```
Applied migration: 0001_create_sessions_table.sql
Applied migration: 0002_create_messages_table.sql
Applied migration: 0003_create_questions_table.sql
Applied migration: 0004_create_responses_table.sql
Applied migration: 0005_create_interruptions_table.sql
Applied migration: 0006_add_status_index_to_sessions.sql
```

Verify:

```bash
sqlite3 app.db ".tables"
```

Expected: `interruptions  messages  questions  responses  schema_migrations  sessions`

### Step D.8 — Verify Idempotency

Run migrations again:

```bash
python3 -c "from app.shared.database.init_db import init_db; init_db()"
```

Expected: no output (nothing to apply). Running `sqlite3 app.db "SELECT COUNT(*) FROM schema_migrations;"` should return `6`.

### Step D.9 — Write the Migration Test

Create `tests/shared/test_migrations.py`:

```python
import os
import sqlite3
import pytest
from app.shared.config.settings import settings


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "database_path", db_path)
    yield db_path


def test_migrations_create_all_tables(fresh_db):
    from app.shared.database.init_db import init_db
    init_db()
    conn = sqlite3.connect(fresh_db)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    expected = {"sessions", "messages", "questions", "responses", "interruptions", "schema_migrations"}
    assert expected.issubset(tables)


def test_migrations_are_idempotent(fresh_db):
    from app.shared.database.init_db import init_db
    init_db()
    init_db()
    conn = sqlite3.connect(fresh_db)
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    conn.close()
    assert count == 6
```

Run:

```bash
pip install pytest
pytest tests/shared/test_migrations.py -v
```

Both tests should pass.

### Phase 1 — Final Check

- [ ] `app/shared/config/settings.py` loads correctly.
- [ ] `app/shared/database/db.py` exists.
- [ ] 6 `.sql` migration files in `app/shared/database/migrations/`.
- [ ] Migration runner creates all tables from scratch.
- [ ] Running twice does not duplicate migrations.
- [ ] `tests/shared/test_migrations.py` passes.

---

<a id="part-e"></a>
## Part E — Phase 2: Session & Message Modules

**Goal of this phase:** build the first two Clean Architecture modules —
session and message — with domain entities, abstract interfaces, use case
classes, and SQLite infrastructure adapters. This proves the pattern
before applying it to the more complex modules.

### Step E.1 — Session Domain Layer

Create `app/modules/session/domain/entities/session_entity.py`:

```python
from dataclasses import dataclass


@dataclass
class Session:
    session_id: str
    start_time: str
    end_time: str | None
    conversation_type: str
    status: str
    current_question_index: int
    current_state: str
    retries: int
```

Create `app/modules/session/domain/interfaces/session_repository_interface.py`:

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
    def close(self, session_id: str, status: str) -> None:
        raise NotImplementedError
```

Notice: the interface is in the **domain** layer. It defines the contract.
It does not import `sqlite3`, `get_connection`, or anything from
infrastructure. It depends on nothing.

### Step E.2 — Session Infrastructure Layer

Create `app/modules/session/infrastructure/persistence/sqlite_session_repository.py`:

```python
from datetime import datetime, timezone
from app.shared.database.db import get_connection
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class SqliteSessionRepository(SessionRepositoryInterface):

    def create(self, session_id: str, conversation_type: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, start_time, conversation_type) VALUES (?, ?, ?)",
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
                "UPDATE sessions SET current_question_index=?, current_state=?, retries=? WHERE session_id=?",
                (index, state, retries, session_id),
            )

    def close(self, session_id: str, status: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET status=?, end_time=?, current_state='completed' WHERE session_id=?",
                (status, datetime.now(timezone.utc).isoformat(), session_id),
            )
```

This is the **adapter** — it implements the domain interface using SQLite.
If you later swap SQLite for PostgreSQL, you write a new adapter here;
nothing else in the session module changes.

### Step E.3 — Session Application Layer (Use Cases)

Create `app/modules/session/application/use_cases/create_session.py`:

```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class CreateSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, conversation_type: str) -> None:
        self._session_repository.create(session_id, conversation_type)
```

Create `app/modules/session/application/use_cases/get_session.py`:

```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class GetSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str) -> dict | None:
        return self._session_repository.get_by_id(session_id)
```

Create `app/modules/session/application/use_cases/update_pointer.py`:

```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class UpdatePointer:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, index: int, state: str, retries: int) -> None:
        self._session_repository.update_pointer(session_id, index, state, retries)
```

Create `app/modules/session/application/use_cases/close_session.py`:

```python
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class CloseSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, status: str) -> None:
        self._session_repository.close(session_id, status)
```

Every use case:
1. Receives its dependency (the repository interface) through the
   constructor — **dependency injection**.
2. Has a single `execute()` method — **one use case, one responsibility**.
3. Depends only on the domain interface, never on `SqliteSessionRepository`
   directly — **dependency inversion**.

### Step E.4 — Test the Session Module

```bash
python3
```

```python
from app.shared.database.init_db import init_db
init_db()

from app.modules.session.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository
from app.modules.session.application.use_cases.create_session import CreateSession
from app.modules.session.application.use_cases.get_session import GetSession

repo = SqliteSessionRepository()
create = CreateSession(repo)
get = GetSession(repo)

create.execute("test-001", "daily_life_companion")
session = get.execute("test-001")
print(session)
# Should show a dict with session_id='test-001', status='active', etc.

# Non-existent session
print(get.execute("nonexistent"))
# Should be None

exit()
```

### Step E.5 — Message Domain Layer

Create `app/modules/message/domain/entities/message_entity.py`:

```python
from dataclasses import dataclass


@dataclass
class Message:
    session_id: str
    sender: str
    text: str
    timestamp: str
```

Create `app/modules/message/domain/interfaces/message_repository_interface.py`:

```python
from abc import ABC, abstractmethod


class MessageRepositoryInterface(ABC):

    @abstractmethod
    def add(self, session_id: str, sender: str, text: str) -> None:
        raise NotImplementedError
```

### Step E.6 — Message Infrastructure Layer

Create `app/modules/message/infrastructure/persistence/sqlite_message_repository.py`:

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
```

### Step E.7 — Message Application Layer

Create `app/modules/message/application/use_cases/add_message.py`:

```python
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface


class AddMessage:

    def __init__(self, message_repository: MessageRepositoryInterface):
        self._message_repository = message_repository

    def execute(self, session_id: str, sender: str, text: str) -> None:
        self._message_repository.add(session_id, sender, text)
```

### Step E.8 — Test the Message Module

```bash
python3
```

```python
from app.modules.message.infrastructure.persistence.sqlite_message_repository import SqliteMessageRepository
from app.modules.message.application.use_cases.add_message import AddMessage

repo = SqliteMessageRepository()
add = AddMessage(repo)
add.execute("test-001", "system", "Hello, what should I call you?")
add.execute("test-001", "user", "My name is Alex")

exit()
```

Verify:

```bash
sqlite3 app.db "SELECT * FROM messages;"
```

Expected: two rows with session_id `test-001`.

### Phase 2 — Final Check

- [ ] Session module has entity, interface, 4 use cases, SQLite adapter.
- [ ] Message module has entity, interface, 1 use case, SQLite adapter.
- [ ] `CreateSession` and `GetSession` work correctly.
- [ ] `AddMessage` writes to the `messages` table.
- [ ] No module directly imports another module's infrastructure.

---

<a id="part-f"></a>
## Part F — Phase 3: Conversation Module (Scripts + Engine)

**Goal of this phase:** build the conversation module — domain entities,
repository interfaces, the conversation engine service (with all 135
hardcoded questions across 4 conversation types), SQLite adapters, and
use cases.

### Step F.1 — Conversation Domain Layer

Create `app/modules/conversation/domain/entities/question_entity.py`:

```python
from dataclasses import dataclass


@dataclass
class Question:
    question_id: int
    conversation_type: str
    question_text: str
    expected_context: str
    sequence: int
```

Create `app/modules/conversation/domain/entities/response_record_entity.py`:

```python
from dataclasses import dataclass


@dataclass
class ResponseRecord:
    question_id: int
    session_id: str
    user_response: str
    validation_result: str
```

Create `app/modules/conversation/domain/interfaces/question_repository_interface.py`:

```python
from abc import ABC, abstractmethod


class QuestionRepositoryInterface(ABC):

    @abstractmethod
    def seed_questions(self, conversation_type: str, items: list[dict]) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_questions(self, conversation_type: str) -> list[dict]:
        raise NotImplementedError
```

Create `app/modules/conversation/domain/interfaces/response_repository_interface.py`:

```python
from abc import ABC, abstractmethod


class ResponseRepositoryInterface(ABC):

    @abstractmethod
    def add(self, question_id: int, session_id: str, user_response: str, validation_result: str) -> None:
        raise NotImplementedError
```

### Step F.2 — Conversation Engine (Application Service)

Create `app/modules/conversation/application/services/conversation_engine.py`.

This file contains the 4 hardcoded scripts (135 total questions) and the
`ConversationEngine` class. The engine receives a
`QuestionRepositoryInterface` through its constructor and uses it to seed
questions into the database.

**See `02-backend-code.md` for the full file** — it is too large to
reproduce here inline (over 400 lines of hardcoded question data). Copy
the entire `conversation_engine.py` code block from that file.

Key points:
- `INTRO_LINES` dict: one intro line per conversation type.
- `SCRIPTS` dict: 30 + 35 + 35 + 35 = 135 questions.
- `ConversationEngine.__init__` takes `QuestionRepositoryInterface`.
- `load_script(type)` seeds questions via the repository (idempotent).
- `get_intro_line(type)` returns the intro sentence.
- `get_current(type, index)` returns the question dict or `None`.
- `is_complete(type, index)` returns `True` if past the last question.

### Step F.3 — Conversation Infrastructure Layer

Create `app/modules/conversation/infrastructure/persistence/sqlite_question_repository.py`:

```python
from app.shared.database.db import get_connection
from app.modules.conversation.domain.interfaces.question_repository_interface import QuestionRepositoryInterface


class SqliteQuestionRepository(QuestionRepositoryInterface):

    def seed_questions(self, conversation_type: str, items: list[dict]) -> None:
        with get_connection() as conn:
            existing = conn.execute(
                "SELECT COUNT(*) c FROM questions WHERE conversation_type=?", (conversation_type,)
            ).fetchone()["c"]
            if existing:
                return
            for item in items:
                conn.execute(
                    "INSERT INTO questions (conversation_type, question_text, expected_context, sequence) VALUES (?, ?, ?, ?)",
                    (conversation_type, item["text"], item["expected_context"], item["sequence"]),
                )

    def get_questions(self, conversation_type: str) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM questions WHERE conversation_type=? ORDER BY sequence ASC",
                (conversation_type,),
            ).fetchall()
            return [dict(r) for r in rows]
```

Create `app/modules/conversation/infrastructure/persistence/sqlite_response_repository.py`:

```python
from app.shared.database.db import get_connection
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface


class SqliteResponseRepository(ResponseRepositoryInterface):

    def add(self, question_id: int, session_id: str, user_response: str, validation_result: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO responses (question_id, session_id, user_response, validation_result) VALUES (?, ?, ?, ?)",
                (question_id, session_id, user_response, validation_result),
            )
```

### Step F.4 — Conversation Use Cases

Create `app/modules/conversation/application/use_cases/load_script.py`:

```python
from app.modules.conversation.application.services.conversation_engine import ConversationEngine


class LoadScript:

    def __init__(self, conversation_engine: ConversationEngine):
        self._conversation_engine = conversation_engine

    def execute(self, conversation_type: str) -> list[dict]:
        return self._conversation_engine.load_script(conversation_type)
```

Create `app/modules/conversation/application/use_cases/get_current_question.py`:

```python
from app.modules.conversation.application.services.conversation_engine import ConversationEngine


class GetCurrentQuestion:

    def __init__(self, conversation_engine: ConversationEngine):
        self._conversation_engine = conversation_engine

    def execute(self, conversation_type: str, index: int) -> dict | None:
        return self._conversation_engine.get_current(conversation_type, index)
```

Create `app/modules/conversation/application/use_cases/check_completion.py`:

```python
from app.modules.conversation.application.services.conversation_engine import ConversationEngine


class CheckCompletion:

    def __init__(self, conversation_engine: ConversationEngine):
        self._conversation_engine = conversation_engine

    def execute(self, conversation_type: str, index: int) -> bool:
        return self._conversation_engine.is_complete(conversation_type, index)
```

Create `app/modules/conversation/application/use_cases/record_response.py`:

```python
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface


class RecordResponse:

    def __init__(self, response_repository: ResponseRepositoryInterface):
        self._response_repository = response_repository

    def execute(self, question_id: int, session_id: str, user_response: str, validation_result: str) -> None:
        self._response_repository.add(question_id, session_id, user_response, validation_result)
```

### Step F.5 — Test the Conversation Module

```bash
python3
```

```python
from app.modules.conversation.infrastructure.persistence.sqlite_question_repository import SqliteQuestionRepository
from app.modules.conversation.application.services.conversation_engine import ConversationEngine

repo = SqliteQuestionRepository()
engine = ConversationEngine(repo)

engine.load_script("daily_life_companion")
engine.load_script("career_life_advisor")
engine.load_script("health_wellness_assistant")
engine.load_script("travel_planner")

exit()
```

Verify:

```bash
sqlite3 app.db "SELECT conversation_type, COUNT(*) FROM questions GROUP BY conversation_type;"
```

Expected:

```
career_life_advisor|35
daily_life_companion|30
health_wellness_assistant|35
travel_planner|35
```

### Step F.6 — Prove Reseeding Is a No-Op

```bash
python3 -c "
from app.modules.conversation.infrastructure.persistence.sqlite_question_repository import SqliteQuestionRepository
from app.modules.conversation.application.services.conversation_engine import ConversationEngine
engine = ConversationEngine(SqliteQuestionRepository())
engine.load_script('daily_life_companion')
"
sqlite3 app.db "SELECT COUNT(*) FROM questions WHERE conversation_type='daily_life_companion';"
```

Expected: still `30`, not `60`.

### Step F.7 — Test Pointer Functions

```bash
python3
```

```python
from app.modules.conversation.infrastructure.persistence.sqlite_question_repository import SqliteQuestionRepository
from app.modules.conversation.application.services.conversation_engine import ConversationEngine

engine = ConversationEngine(SqliteQuestionRepository())

print(engine.get_current("daily_life_companion", 0))    # first question dict
print(engine.get_current("daily_life_companion", 29))   # last question dict
print(engine.get_current("daily_life_companion", 30))   # None
print(engine.is_complete("daily_life_companion", 30))    # True
print(engine.is_complete("daily_life_companion", 29))    # False
exit()
```

### Phase 3 — Final Check

- [ ] `conversation_engine.py` exists with all 135 questions.
- [ ] `questions` table has exactly 135 rows (30/35/35/35).
- [ ] Reseeding does not duplicate rows.
- [ ] `get_current`/`is_complete` behave correctly at edges.

---

<a id="part-g"></a>
## Part G — Phase 4: Voice Module (Deepgram STT/TTS)

**Goal of this phase:** build the voice module with domain interfaces,
Deepgram infrastructure adapters, and application use cases. Test STT and
TTS in isolation before wiring into anything else.

### Step G.1 — Voice Domain Layer (Interfaces)

Create `app/modules/voice/domain/interfaces/stt_provider_interface.py`:

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
    async def receive_transcript(self) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
```

Create `app/modules/voice/domain/interfaces/tts_provider_interface.py`:

```python
from abc import ABC, abstractmethod


class TTSProviderInterface(ABC):

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        raise NotImplementedError
```

These interfaces define the contract. If you later swap Deepgram for
Google Cloud Speech or AWS Polly, you write new adapters implementing
these same interfaces — nothing else in the voice module or the
entrypoints changes.

### Step G.2 — Voice Infrastructure Layer (Deepgram Adapters)

Create `app/modules/voice/infrastructure/external/deepgram_stt_adapter.py`:

```python
import json
import websockets
from app.shared.config.settings import settings
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface

DEEPGRAM_STT_URL = "wss://api.deepgram.com/v1/listen?punctuate=true&interim_results=false"


class DeepgramSTTAdapter(STTProviderInterface):

    def __init__(self):
        self._ws = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            DEEPGRAM_STT_URL,
            extra_headers={"Authorization": f"Token {settings.deepgram_api_key}"},
        )

    async def send_audio(self, chunk: bytes) -> None:
        await self._ws.send(chunk)

    async def receive_transcript(self) -> str | None:
        message = await self._ws.recv()
        data = json.loads(message)
        alt = data.get("channel", {}).get("alternatives", [{}])[0]
        transcript = alt.get("transcript", "")
        return transcript if data.get("is_final") and transcript else None

    async def close(self) -> None:
        if self._ws:
            await self._ws.close()
```

Create `app/modules/voice/infrastructure/external/deepgram_tts_adapter.py`:

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

### Step G.3 — Voice Application Layer (Use Cases)

Create `app/modules/voice/application/use_cases/synthesize_speech.py`:

```python
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface


class SynthesizeSpeech:

    def __init__(self, tts_provider: TTSProviderInterface):
        self._tts_provider = tts_provider

    async def execute(self, text: str) -> bytes:
        return await self._tts_provider.synthesize(text)
```

Create `app/modules/voice/application/use_cases/stream_speech_to_text.py`:

```python
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface


class StreamSpeechToText:

    def __init__(self, stt_provider: STTProviderInterface):
        self._stt_provider = stt_provider

    async def connect(self) -> None:
        await self._stt_provider.connect()

    async def send_audio(self, chunk: bytes) -> None:
        await self._stt_provider.send_audio(chunk)

    async def receive_transcript(self) -> str | None:
        return await self._stt_provider.receive_transcript()

    async def close(self) -> None:
        await self._stt_provider.close()
```

### Step G.4 — Smoke-Test TTS

```bash
python3
```

```python
import asyncio
from app.modules.voice.infrastructure.external.deepgram_tts_adapter import DeepgramTTSAdapter
from app.modules.voice.application.use_cases.synthesize_speech import SynthesizeSpeech

async def main():
    adapter = DeepgramTTSAdapter()
    use_case = SynthesizeSpeech(adapter)
    audio = await use_case.execute("Hello, this is a test.")
    with open("test_output.mp3", "wb") as f:
        f.write(audio)
    print(f"Got {len(audio)} bytes of audio")

asyncio.run(main())
exit()
```

Expected: `Got NNNN bytes of audio` and a playable `test_output.mp3`.

On macOS: `afplay test_output.mp3`

### Step G.5 — Smoke-Test STT

Record a short `.wav` of yourself saying a few words, save as
`test_input.wav` in `backend/`.

```bash
python3
```

```python
import asyncio
from app.modules.voice.infrastructure.external.deepgram_stt_adapter import DeepgramSTTAdapter

async def main():
    stt = DeepgramSTTAdapter()
    await stt.connect()
    with open("test_input.wav", "rb") as f:
        audio_bytes = f.read()
    await stt.send_audio(audio_bytes)
    transcript = None
    for _ in range(10):
        transcript = await stt.receive_transcript()
        if transcript:
            break
    print("Transcript:", transcript)
    await stt.close()

asyncio.run(main())
exit()
```

Expected: `Transcript:` followed by recognizable words.

### Phase 4 — Final Check

- [ ] `STTProviderInterface` and `TTSProviderInterface` defined in domain.
- [ ] `DeepgramSTTAdapter` and `DeepgramTTSAdapter` in infrastructure.
- [ ] `SynthesizeSpeech` and `StreamSpeechToText` use cases in application.
- [ ] TTS returns playable audio bytes.
- [ ] STT returns a real transcript.
- [ ] Both verified in isolation — proving Deepgram works before wiring.

---

<a id="part-h"></a>
## Part H — Phase 5: Interruption Module + AI Validation

**Goal of this phase:** build the interruption module (pattern matching,
no AI) and the AI validation use case in the conversation module.

### Step H.1 — Interruption Domain Layer

Create `app/modules/interruption/domain/entities/interruption_entity.py`:

```python
from dataclasses import dataclass


@dataclass
class Interruption:
    session_id: str
    interruption_type: str
    interruption_text: str
    timestamp: str
```

Create `app/modules/interruption/domain/interfaces/interruption_repository_interface.py`:

```python
from abc import ABC, abstractmethod


class InterruptionRepositoryInterface(ABC):

    @abstractmethod
    def add(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        raise NotImplementedError
```

### Step H.2 — Interruption Application Layer

Create `app/modules/interruption/application/use_cases/classify_interruption.py`:

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

Create `app/modules/interruption/application/use_cases/record_interruption.py`:

```python
from app.modules.interruption.domain.interfaces.interruption_repository_interface import InterruptionRepositoryInterface


class RecordInterruption:

    def __init__(self, interruption_repository: InterruptionRepositoryInterface):
        self._interruption_repository = interruption_repository

    def execute(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        self._interruption_repository.add(session_id, interruption_type, interruption_text)
```

### Step H.3 — Interruption Infrastructure Layer

Create `app/modules/interruption/infrastructure/persistence/sqlite_interruption_repository.py`:

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

### Step H.4 — Test Interruption Classification

```bash
python3
```

```python
from app.modules.interruption.application.use_cases.classify_interruption import ClassifyInterruption

classify = ClassifyInterruption()

print(classify.execute("stop"))                     # stop
print(classify.execute("Cancel"))                   # cancel
print(classify.execute("repeat"))                   # repeat
print(classify.execute("No, actually apple"))       # correction
print(classify.execute("my day was fine"))           # None
exit()
```

Expected: `stop`, `cancel`, `repeat`, `correction`, `None`.

### Step H.5 — AI Validation Use Case (Conversation Module)

Create `app/modules/conversation/application/use_cases/validate_response.py`:

```python
import json
import httpx
from app.shared.config.settings import settings


VALIDATION_PROMPT = """You validate one turn of a scripted voice conversation.
Item type: {item_type}
Expected context: {expected_context}
User response: {user_response}

If item_type is "instruction", determine ONLY whether the user expressed completion
intent (e.g. done, finished, yes, ready). Do not judge whether the action occurred.
If item_type is "question", determine ONLY whether the response is topically relevant
to the expected context. Do not judge factual correctness.

Respond with strict JSON only: {{"valid": true|false, "reason": "<short reason>"}}"""


class ValidateResponse:

    async def execute(self, item_type: str, expected_context: str, user_response: str) -> dict:
        prompt = VALIDATION_PROMPT.format(
            item_type=item_type, expected_context=expected_context, user_response=user_response
        )
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"content-type": "application/json"},
                    json={
                        "model": settings.ai_validation_model,
                        "max_tokens": 200,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                resp.raise_for_status()
                text = resp.json()["content"][0]["text"]
                return json.loads(text)
            except Exception:
                return {"valid": False, "reason": "validation_unavailable"}
```

### Step H.6 — Test AI Validation

```bash
python3
```

```python
import asyncio
from app.modules.conversation.application.use_cases.validate_response import ValidateResponse

async def main():
    validate = ValidateResponse()
    good = await validate.execute("question", "a wake-up time", "around 7am")
    print("good:", good)
    bad = await validate.execute("question", "a wake-up time", "I like pizza")
    print("bad:", bad)

asyncio.run(main())
exit()
```

Expected: `good: {"valid": True, ...}`, `bad: {"valid": False, ...}`.

### Phase 5 — Final Check

- [ ] `ClassifyInterruption` returns correct labels for all 5 test cases.
- [ ] `ValidateResponse` returns `{"valid": bool, "reason": str}`.
- [ ] Neither needed a WebSocket or Deepgram to test — properly isolated.

---

<a id="part-i"></a>
## Part I — Phase 6: Entrypoints (WebSocket Handler + HTTP)

**Goal of this phase:** build the presentation layer — the connection
manager, response formatter, HTTP health endpoint, and the WebSocket
conversation handler that wires all modules together using dependency
injection.

### Step I.1 — Connection Manager

Create `app/entrypoints/websocket/connection_manager.py`:

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

### Step I.2 — Response Formatter

Create `app/entrypoints/response_formatter.py`:

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

### Step I.3 — HTTP Health Endpoint

Create `app/entrypoints/http/health.py`:

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}
```

### Step I.4 — WebSocket Conversation Handler

This is the largest single file — the "traffic cop" that owns the
lifecycle of one WebSocket connection. It contains no business logic;
all decisions live in the use cases. Its job is:

1. Instantiate infrastructure adapters (concrete implementations).
2. Inject them into application use cases (dependency injection).
3. Orchestrate the conversation loop by invoking use cases.

Create `app/entrypoints/websocket/conversation_handler.py`:

```python
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.entrypoints.websocket.connection_manager import manager
from app.entrypoints import response_formatter as fmt
from app.shared.config.settings import settings

# Infrastructure adapters (concrete implementations)
from app.modules.session.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository
from app.modules.message.infrastructure.persistence.sqlite_message_repository import SqliteMessageRepository
from app.modules.conversation.infrastructure.persistence.sqlite_question_repository import SqliteQuestionRepository
from app.modules.conversation.infrastructure.persistence.sqlite_response_repository import SqliteResponseRepository
from app.modules.interruption.infrastructure.persistence.sqlite_interruption_repository import SqliteInterruptionRepository
from app.modules.voice.infrastructure.external.deepgram_stt_adapter import DeepgramSTTAdapter
from app.modules.voice.infrastructure.external.deepgram_tts_adapter import DeepgramTTSAdapter

# Application use cases
from app.modules.session.application.use_cases.create_session import CreateSession
from app.modules.session.application.use_cases.get_session import GetSession
from app.modules.session.application.use_cases.update_pointer import UpdatePointer
from app.modules.session.application.use_cases.close_session import CloseSession
from app.modules.message.application.use_cases.add_message import AddMessage
from app.modules.conversation.application.services.conversation_engine import ConversationEngine
from app.modules.conversation.application.use_cases.validate_response import ValidateResponse
from app.modules.conversation.application.use_cases.record_response import RecordResponse
from app.modules.interruption.application.use_cases.classify_interruption import ClassifyInterruption
from app.modules.interruption.application.use_cases.record_interruption import RecordInterruption
from app.modules.voice.application.use_cases.synthesize_speech import SynthesizeSpeech

router = APIRouter()


@router.websocket("/ws/{conversation_type}/{session_id}")
async def conversation_socket(ws: WebSocket, conversation_type: str, session_id: str):
    # --- Dependency Injection: wire adapters into use cases ---
    session_repo = SqliteSessionRepository()
    message_repo = SqliteMessageRepository()
    question_repo = SqliteQuestionRepository()
    response_repo = SqliteResponseRepository()
    interruption_repo = SqliteInterruptionRepository()
    tts_adapter = DeepgramTTSAdapter()
    stt_adapter = DeepgramSTTAdapter()

    create_session = CreateSession(session_repo)
    get_session = GetSession(session_repo)
    update_pointer = UpdatePointer(session_repo)
    close_session = CloseSession(session_repo)
    add_message = AddMessage(message_repo)
    conversation_engine = ConversationEngine(question_repo)
    validate_response = ValidateResponse()
    record_response = RecordResponse(response_repo)
    classify_interruption = ClassifyInterruption()
    record_interruption = RecordInterruption(interruption_repo)
    synthesize_speech = SynthesizeSpeech(tts_adapter)

    # --- Connection setup ---
    await manager.connect(session_id, ws)

    session = get_session.execute(session_id)
    if not session:
        create_session.execute(session_id, conversation_type)
        conversation_engine.load_script(conversation_type)
        index, retries = 0, 0
    else:
        index, retries = session["current_question_index"], session["retries"]

    await stt_adapter.connect()

    # --- Helper: speak text via TTS ---
    async def speak(text: str):
        add_message.execute(session_id, "system", text)
        audio = await synthesize_speech.execute(text)
        await manager.send_json(session_id, fmt.event("tts_audio_meta", {"text": text}))
        await manager.send_bytes(session_id, audio)

    # --- Helper: ask current question ---
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

    # --- Session start ---
    await manager.send_json(session_id, fmt.event("session_started", {"session_id": session_id}))
    await speak(conversation_engine.get_intro_line(conversation_type))
    if not await ask_current():
        return

    # --- Main conversation loop ---
    try:
        while True:
            frame = await ws.receive()
            if "bytes" in frame and frame["bytes"] is not None:
                await stt_adapter.send_audio(frame["bytes"])
                continue

            transcript = await stt_adapter.receive_transcript()
            if not transcript:
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
                # operative text is this transcript itself; fall through to validation

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
        pass
    finally:
        await stt_adapter.close()
        manager.disconnect(session_id)
```

### Step I.5 — Test with a Plain WebSocket Client

Create a temporary `main.py` so `uvicorn` can run:

```python
# backend/main.py (temporary for this test)
from fastapi import FastAPI
from app.entrypoints.websocket.conversation_handler import router as ws_router
from app.shared.database.init_db import init_db

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    init_db()

app.include_router(ws_router)
```

Start the server:

```bash
uvicorn main:app --reload --port 8000
```

In a **second terminal** (venv active), create `ws_smoke_test.py`:

```python
import asyncio
import json
import uuid
import websockets

async def main():
    session_id = str(uuid.uuid4())
    url = f"ws://localhost:8000/ws/daily_life_companion/{session_id}"
    async with websockets.connect(url) as ws:
        for _ in range(6):
            msg = await ws.recv()
            if isinstance(msg, bytes):
                print(f"[binary audio frame, {len(msg)} bytes]")
            else:
                print("[json]", json.loads(msg))

asyncio.run(main())
```

Run: `python3 ws_smoke_test.py`

Expected output:

```
[json] {'event': 'session_started', 'payload': {'session_id': '...'}}
[json] {'event': 'tts_audio_meta', 'payload': {'text': "I'd love to know how your day is going."}}
[binary audio frame, NNNN bytes]
[json] {'event': 'question', 'payload': {'text': 'What should I call you?', 'sequence': 0}}
[json] {'event': 'tts_audio_meta', 'payload': {'text': 'What should I call you?'}}
[binary audio frame, NNNN bytes]
```

### Phase 6 — Final Check

- [ ] `connection_manager.py`, `response_formatter.py`, `conversation_handler.py`, `health.py` all exist.
- [ ] WebSocket smoke test receives events in correct order.
- [ ] A session row exists in `sessions` table.

---

<a id="part-j"></a>
## Part J — Phase 7: Application Assembly

**Goal of this phase:** finalize supporting files and write the real
`main.py`.

### Step J.1 — Write Shared Constants

Create `app/shared/constants/conversation_types.py`:

```python
CONVERSATION_TYPES = [
    "daily_life_companion",
    "career_life_advisor",
    "health_wellness_assistant",
    "travel_planner",
]
```

Create `app/shared/constants/states.py`:

```python
STATES = [
    "welcoming",
    "asking",
    "listening",
    "validating",
    "speaking",
    "repeating",
    "completed",
]
```

Create `app/shared/constants/interruption_types.py`:

```python
INTERRUPTION_TYPES = ["stop", "cancel", "repeat", "correction"]
```

### Step J.2 — Write Shared Logger

Create `app/shared/logging/logger.py`:

```python
import logging

logger = logging.getLogger("conversation_widget")
logging.basicConfig(level=logging.INFO)
```

### Step J.3 — Write Shared Exceptions

Create `app/shared/exceptions/domain_exceptions.py`:

```python
class ConversationTypeNotFoundError(Exception):
    pass


class SessionNotFoundError(Exception):
    pass


class ScriptAlreadyLoadedError(Exception):
    pass
```

### Step J.4 — Write Shared Schemas

Create `app/shared/schemas/session_schema.py`:

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

Create `app/shared/schemas/message_schema.py`:

```python
from pydantic import BaseModel


class MessageIn(BaseModel):
    session_id: str
    sender: str
    text: str
```

Create `app/shared/schemas/ws_schema.py`:

```python
from pydantic import BaseModel
from typing import Optional, Literal


class WSEvent(BaseModel):
    event: Literal[
        "session_started", "question", "instruction", "validation_result",
        "tts_audio", "tts_stop", "session_completed", "session_cancelled", "error"
    ]
    payload: Optional[dict] = None
```

### Step J.5 — Write the Final `main.py`

Replace the temporary version:

```python
from fastapi import FastAPI
from app.entrypoints.websocket.conversation_handler import router as ws_router
from app.entrypoints.http.health import router as health_router
from app.shared.database.init_db import init_db

app = FastAPI(title="Conversational Widget Backend")


@app.on_event("startup")
async def on_startup():
    init_db()


app.include_router(health_router)
app.include_router(ws_router)
```

### Step J.6 — Run and Verify

```bash
uvicorn main:app --reload --port 8000
```

Test health:

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

### Phase 7 — Final Check

- [ ] All shared files (constants, logger, exceptions, schemas) exist.
- [ ] Final `main.py` in place.
- [ ] Server boots cleanly with migrations.
- [ ] Health endpoint responds.

---

<a id="part-k"></a>
## Part K — Phase 8: Backend Test Suite

### Step K.1 — Test Conversation Engine

Create `tests/modules/conversation/test_conversation_engine.py`:

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


def test_load_and_count():
    from app.modules.conversation.infrastructure.persistence.sqlite_question_repository import SqliteQuestionRepository
    from app.modules.conversation.application.services.conversation_engine import ConversationEngine

    engine = ConversationEngine(SqliteQuestionRepository())
    items = engine.load_script("daily_life_companion")
    assert len(items) == 30


def test_get_current_returns_none_past_end():
    from app.modules.conversation.infrastructure.persistence.sqlite_question_repository import SqliteQuestionRepository
    from app.modules.conversation.application.services.conversation_engine import ConversationEngine

    engine = ConversationEngine(SqliteQuestionRepository())
    engine.load_script("daily_life_companion")
    assert engine.get_current("daily_life_companion", 30) is None


def test_is_complete():
    from app.modules.conversation.infrastructure.persistence.sqlite_question_repository import SqliteQuestionRepository
    from app.modules.conversation.application.services.conversation_engine import ConversationEngine

    engine = ConversationEngine(SqliteQuestionRepository())
    engine.load_script("daily_life_companion")
    assert not engine.is_complete("daily_life_companion", 29)
    assert engine.is_complete("daily_life_companion", 30)
```

### Step K.2 — Test Interruption Classification

Create `tests/modules/interruption/test_classify_interruption.py`:

```python
from app.modules.interruption.application.use_cases.classify_interruption import ClassifyInterruption


def test_stop():
    c = ClassifyInterruption()
    assert c.execute("stop") == "stop"
    assert c.execute("STOP") == "stop"
    assert c.execute("wait") == "stop"
    assert c.execute("hold on") == "stop"


def test_cancel():
    c = ClassifyInterruption()
    assert c.execute("cancel") == "cancel"
    assert c.execute("end session") == "cancel"
    assert c.execute("quit") == "cancel"


def test_repeat():
    c = ClassifyInterruption()
    assert c.execute("repeat") == "repeat"
    assert c.execute("say that again") == "repeat"
    assert c.execute("come again") == "repeat"


def test_correction():
    c = ClassifyInterruption()
    assert c.execute("no, apple") == "correction"
    assert c.execute("actually, it was blue") == "correction"
    assert c.execute("i meant red") == "correction"


def test_normal_answer():
    c = ClassifyInterruption()
    assert c.execute("my day was fine") is None
    assert c.execute("seven o'clock") is None
```

### Step K.3 — Run All Tests

```bash
pytest tests/ -v
```

All tests should pass.

### Phase 8 — Final Check

- [ ] `test_migrations.py` passes.
- [ ] `test_conversation_engine.py` passes.
- [ ] `test_classify_interruption.py` passes.
- [ ] All green before touching frontend.

---

<a id="part-l"></a>
## Part L — Phase 9: Frontend

**Goal:** build the React frontend. See `03-frontend-code.md` for
complete code blocks. This guide covers the setup and file creation order.

### Step L.1 — Initialize the Frontend

```bash
cd frontend
npm init vite@latest ./ -- --template react
npm install
```

### Step L.2 — Create Environment

```bash
cp .env.example .env
```

Or create `.env` manually:

```
VITE_WS_BASE_URL=ws://localhost:8000
```

### Step L.3 — Create Files (in order)

Create each file from `03-frontend-code.md`:

1. `src/context/ConversationContext.jsx`
2. `src/utils/audioUtils.js`
3. `src/services/websocketService.js`
4. `src/hooks/useDeepgramAudio.js`
5. `src/hooks/useWebSocket.js`
6. `src/components/WidgetButton.jsx`
7. `src/components/Transcript.jsx`
8. `src/components/SpeakingIndicator.jsx`
9. `src/components/ListeningIndicator.jsx`
10. `src/components/SessionEndedState.jsx`
11. `src/components/ConversationWindow.jsx`
12. `src/pages/HomePage.jsx`
13. `src/App.jsx`

### Step L.4 — Start the Frontend

```bash
npm run dev
```

Open `http://localhost:3000` in your browser. You should see the
"Talk to Assistant" button.

### Step L.5 — Test End-to-End

1. Make sure the backend is running (`uvicorn main:app --reload --port 8000`).
2. Click "Talk to Assistant".
3. Grant microphone permission when prompted.
4. You should hear the intro line and first question.
5. Speak your answer. The widget should display the transcript and
   proceed to the next question.

### Phase 9 — Final Check

- [ ] Frontend starts without errors.
- [ ] Widget opens and connects to backend.
- [ ] Audio plays through TTS.
- [ ] Mic input is captured and transcribed.

---

<a id="part-m"></a>
## Part M — Phase 10: Integration Test

### Step M.1 — Backend Integration Test

Create `tests/integration/test_websocket_flow.py`:

```python
import asyncio
import json
import uuid
import pytest
import websockets


@pytest.mark.asyncio
async def test_session_started_event():
    """Connect and verify we get session_started as the first event."""
    session_id = str(uuid.uuid4())
    url = f"ws://localhost:8000/ws/daily_life_companion/{session_id}"
    async with websockets.connect(url) as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(msg)
        assert data["event"] == "session_started"
        assert data["payload"]["session_id"] == session_id
```

Run (with server running in another terminal):

```bash
pip install pytest-asyncio
pytest tests/integration/test_websocket_flow.py -v
```

### Phase 10 — Final Check

- [ ] Integration test passes against running server.
- [ ] Full end-to-end flow verified manually.
- [ ] All backend tests green.

---

## Complete File Listing

After following all phases, your `backend/` directory should contain:

```
backend/
  app/
    __init__.py
    modules/
      __init__.py
      session/
        __init__.py
        domain/
          __init__.py
          entities/
            __init__.py
            session_entity.py
          interfaces/
            __init__.py
            session_repository_interface.py
        application/
          __init__.py
          use_cases/
            __init__.py
            create_session.py
            get_session.py
            update_pointer.py
            close_session.py
        infrastructure/
          __init__.py
          persistence/
            __init__.py
            sqlite_session_repository.py
      message/
        __init__.py
        domain/
          __init__.py
          entities/
            __init__.py
            message_entity.py
          interfaces/
            __init__.py
            message_repository_interface.py
        application/
          __init__.py
          use_cases/
            __init__.py
            add_message.py
        infrastructure/
          __init__.py
          persistence/
            __init__.py
            sqlite_message_repository.py
      conversation/
        __init__.py
        domain/
          __init__.py
          entities/
            __init__.py
            question_entity.py
            response_record_entity.py
          interfaces/
            __init__.py
            question_repository_interface.py
            response_repository_interface.py
        application/
          __init__.py
          use_cases/
            __init__.py
            load_script.py
            get_current_question.py
            check_completion.py
            validate_response.py
            record_response.py
          services/
            __init__.py
            conversation_engine.py
        infrastructure/
          __init__.py
          persistence/
            __init__.py
            sqlite_question_repository.py
            sqlite_response_repository.py
          external/
            __init__.py
            anthropic_validation_client.py
      voice/
        __init__.py
        domain/
          __init__.py
          interfaces/
            __init__.py
            stt_provider_interface.py
            tts_provider_interface.py
        application/
          __init__.py
          use_cases/
            __init__.py
            stream_speech_to_text.py
            synthesize_speech.py
        infrastructure/
          __init__.py
          external/
            __init__.py
            deepgram_stt_adapter.py
            deepgram_tts_adapter.py
      interruption/
        __init__.py
        domain/
          __init__.py
          entities/
            __init__.py
            interruption_entity.py
          interfaces/
            __init__.py
            interruption_repository_interface.py
        application/
          __init__.py
          use_cases/
            __init__.py
            classify_interruption.py
            record_interruption.py
        infrastructure/
          __init__.py
          persistence/
            __init__.py
            sqlite_interruption_repository.py
    shared/
      __init__.py
      database/
        __init__.py
        db.py
        init_db.py
        migrations/
          __init__.py
          runner.py
          0001_create_sessions_table.sql
          0002_create_messages_table.sql
          0003_create_questions_table.sql
          0004_create_responses_table.sql
          0005_create_interruptions_table.sql
          0006_add_status_index_to_sessions.sql
      config/
        __init__.py
        settings.py
      constants/
        __init__.py
        conversation_types.py
        states.py
        interruption_types.py
      logging/
        __init__.py
        logger.py
      schemas/
        __init__.py
        ws_schema.py
        session_schema.py
        message_schema.py
      exceptions/
        __init__.py
        domain_exceptions.py
    entrypoints/
      __init__.py
      response_formatter.py
      websocket/
        __init__.py
        connection_manager.py
        conversation_handler.py
      http/
        __init__.py
        health.py
  tests/
    __init__.py
    modules/
      __init__.py
      session/
        __init__.py
        test_session_use_cases.py
      conversation/
        __init__.py
        test_conversation_engine.py
      interruption/
        __init__.py
        test_classify_interruption.py
    shared/
      __init__.py
      test_migrations.py
    integration/
      __init__.py
      test_websocket_flow.py
  main.py
  requirements.txt
  .env
  .gitignore
```

Each module is self-contained with its own domain, application, and
infrastructure layers. Dependencies always point inward toward the Domain.
Infrastructure adapters implement Domain interfaces. Use cases receive
dependencies through constructor injection. The presentation layer
(entrypoints) wires everything together without containing business logic.
