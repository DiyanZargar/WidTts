-- Interruptions table (SQLite)
CREATE TABLE IF NOT EXISTS interruptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    turn_id TEXT,
    transcript TEXT NOT NULL DEFAULT '',
    interrupt_type TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.0,
    action_taken TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_interruptions_session ON interruptions(session_id);
