# Database Migrations

Migrations live under the **shared** layer since the database is a
cross-cutting concern used by all modules' infrastructure adapters.

Path: `backend/app/shared/database/migrations/`

## Migration Files

All six `.sql` migration files are placed in
`app/shared/database/migrations/` and executed in lexicographic order by
the runner. Each is forward-only and idempotent (`IF NOT EXISTS`).

### 0001_create_sessions_table.sql

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

### 0002_create_messages_table.sql

```sql
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    sender TEXT NOT NULL CHECK (sender IN ('system','user')),
    text TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

### 0003_create_questions_table.sql

```sql
CREATE TABLE IF NOT EXISTS questions (
    question_id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_type TEXT NOT NULL,
    question_text TEXT NOT NULL,
    expected_context TEXT NOT NULL,
    sequence INTEGER NOT NULL
);
```

### 0004_create_responses_table.sql

```sql
CREATE TABLE IF NOT EXISTS responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER NOT NULL REFERENCES questions(question_id),
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    user_response TEXT NOT NULL,
    validation_result TEXT NOT NULL CHECK (validation_result IN ('valid','invalid'))
);
```

### 0005_create_interruptions_table.sql

```sql
CREATE TABLE IF NOT EXISTS interruptions (
    interruption_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    interruption_type TEXT NOT NULL CHECK (interruption_type IN ('stop','cancel','repeat','correction')),
    interruption_text TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

### 0006_add_status_index_to_sessions.sql

```sql
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
```

---

## Migration Runner

Path: `app/shared/database/migrations/runner.py`

The runner tracks which migrations have been applied in a
`schema_migrations` table and only executes new ones.

```python
import os
import sqlite3
from app.shared.config.settings import settings


def run_migrations():
    migration_dir = os.path.join(os.path.dirname(__file__))
    conn = sqlite3.connect(settings.database_path)
    conn.execute("PRAGMA foreign_keys = ON")

    # Create the tracking table if it doesn't exist
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()

    # Get already-applied migrations
    applied = {
        row[0]
        for row in conn.execute("SELECT filename FROM schema_migrations").fetchall()
    }

    # Find and sort .sql files
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

---

## Database Connection Helper

Path: `app/shared/database/db.py`

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

---

## Database Initialization

Path: `app/shared/database/init_db.py`

Called by `main.py` on startup to ensure all migrations are applied.

```python
from app.shared.database.migrations.runner import run_migrations


def init_db():
    run_migrations()
```

---

## Migration Tests

Path: `backend/tests/shared/test_migrations.py`

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
    init_db()  # running twice should not raise
    conn = sqlite3.connect(fresh_db)
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    conn.close()
    assert count == 6  # exactly 6 migration files
```

---

## CLI Verification Commands

After running the server at least once (or calling `init_db()` manually):

```bash
# List all tables
sqlite3 app.db ".tables"
# Expected: interruptions  messages  questions  responses  schema_migrations  sessions

# Show sessions schema
sqlite3 app.db ".schema sessions"

# Show applied migrations
sqlite3 app.db "SELECT * FROM schema_migrations;"

# Count questions per type (after conversation engine seeds them)
sqlite3 app.db "SELECT conversation_type, COUNT(*) FROM questions GROUP BY conversation_type;"
# Expected: career_life_advisor|35  daily_life_companion|30  health_wellness_assistant|35  travel_planner|35
```
