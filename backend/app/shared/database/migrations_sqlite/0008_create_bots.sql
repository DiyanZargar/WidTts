-- Bots table (SQLite)
CREATE TABLE IF NOT EXISTS bots (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    personality TEXT NOT NULL DEFAULT '',
    system_prompt TEXT NOT NULL DEFAULT '',
    llm_provider_id TEXT REFERENCES llm_providers(id) ON DELETE SET NULL,
    llm_model TEXT NOT NULL DEFAULT '',
    speech_provider_id TEXT REFERENCES speech_providers(id) ON DELETE SET NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Only one bot can be active at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_bot
    ON bots (is_active) WHERE is_active = 1;

-- FK from sessions to bots
-- SQLite doesn't support ALTER TABLE ADD CONSTRAINT, so we rely on
-- the bot_id column in sessions already defined as TEXT.
-- The FK is enforced at the application level.
