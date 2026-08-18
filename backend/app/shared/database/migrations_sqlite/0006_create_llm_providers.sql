-- LLM providers table (SQLite)
CREATE TABLE IF NOT EXISTS llm_providers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    base_url TEXT NOT NULL DEFAULT '',
    credentials_enc TEXT NOT NULL DEFAULT '{}',
    key_version INTEGER NOT NULL DEFAULT 1 REFERENCES encryption_keys(key_version),
    available_models TEXT NOT NULL DEFAULT '[]',
    last_test_status TEXT NOT NULL DEFAULT 'untested',
    last_test_at TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_default_llm
    ON llm_providers (is_default) WHERE is_default = 1;
