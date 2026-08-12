CREATE TABLE IF NOT EXISTS realtime_runtime_config (
    id TEXT PRIMARY KEY,
    server_url TEXT NOT NULL,
    encrypted_api_key TEXT NOT NULL,
    encrypted_api_secret TEXT NOT NULL,
    room_token_ttl_seconds INTEGER NOT NULL DEFAULT 3600,
    audio_sample_rate INTEGER NOT NULL DEFAULT 16000,
    last_tested_at TEXT,
    last_test_status TEXT,
    last_test_error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
