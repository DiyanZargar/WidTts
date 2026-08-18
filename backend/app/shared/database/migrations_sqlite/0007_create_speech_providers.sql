-- Speech providers table (SQLite)
CREATE TABLE IF NOT EXISTS speech_providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    credentials_enc TEXT NOT NULL DEFAULT '{}',
    key_version INTEGER NOT NULL DEFAULT 1 REFERENCES encryption_keys(key_version),
    stt_model TEXT NOT NULL DEFAULT '',
    stt_language TEXT NOT NULL DEFAULT 'en',
    stt_extra TEXT NOT NULL DEFAULT '{}',
    tts_model TEXT NOT NULL DEFAULT '',
    tts_voice_id TEXT NOT NULL DEFAULT '',
    tts_extra TEXT NOT NULL DEFAULT '{}',
    last_test_status TEXT NOT NULL DEFAULT 'untested',
    last_test_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
