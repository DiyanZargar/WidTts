CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'anonymous',
    start_time TEXT NOT NULL,
    end_time TEXT,
    conversation_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    current_question_index INTEGER NOT NULL DEFAULT 0,
    current_state TEXT NOT NULL DEFAULT 'welcoming',
    retries INTEGER NOT NULL DEFAULT 0
);
