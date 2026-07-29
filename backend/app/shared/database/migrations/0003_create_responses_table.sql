CREATE TABLE IF NOT EXISTS responses (
    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    sequence INTEGER NOT NULL,
    user_response TEXT NOT NULL,
    validation_result TEXT NOT NULL CHECK (validation_result IN ('valid','invalid'))
);
