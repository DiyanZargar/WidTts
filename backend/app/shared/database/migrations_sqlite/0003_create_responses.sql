-- Responses table (SQLite)
CREATE TABLE IF NOT EXISTS responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    turn_id TEXT,
    question_id TEXT,
    transcript TEXT NOT NULL DEFAULT '',
    classification TEXT NOT NULL DEFAULT '',
    should_advance INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_responses_session ON responses(session_id);
