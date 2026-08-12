-- Sessions table (SQLite)
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT '',
    conversation_type TEXT NOT NULL DEFAULT '',
    bot_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    current_question_index INTEGER NOT NULL DEFAULT 0,
    current_state TEXT NOT NULL DEFAULT 'IDLE',
    retries INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    closed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_bot_id ON sessions(bot_id);
