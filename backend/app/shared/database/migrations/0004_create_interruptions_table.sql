CREATE TABLE IF NOT EXISTS interruptions (
    interruption_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    interruption_type TEXT NOT NULL CHECK (interruption_type IN ('stop','cancel','repeat','correction')),
    interruption_text TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
