-- Bots table
CREATE TABLE IF NOT EXISTS bots (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    personality TEXT NOT NULL DEFAULT '',

    -- System prompt containing all conversation/interview logic
    system_prompt TEXT NOT NULL DEFAULT '',

    -- Provider references
    llm_provider_id TEXT REFERENCES llm_providers(id) ON DELETE SET NULL,
    llm_model TEXT NOT NULL DEFAULT '',
    speech_provider_id TEXT REFERENCES speech_providers(id) ON DELETE SET NULL,

    -- Activation
    is_active BOOLEAN NOT NULL DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Only one bot can be active at a time
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_bot
    ON bots (is_active) WHERE is_active = TRUE;

-- FK from sessions to bots
ALTER TABLE sessions
    ADD CONSTRAINT fk_sessions_bot FOREIGN KEY (bot_id) REFERENCES bots(id) ON DELETE SET NULL;
