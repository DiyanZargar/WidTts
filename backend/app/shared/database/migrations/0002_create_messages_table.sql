CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    sender TEXT NOT NULL CHECK (sender IN ('system','user')),
    text TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
