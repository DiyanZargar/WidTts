-- LLM providers table
CREATE TABLE IF NOT EXISTS llm_providers (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,  -- 'openai' | 'anthropic' | 'google' | 'openai_compatible'
    base_url TEXT NOT NULL DEFAULT '',
    credentials_enc JSONB NOT NULL DEFAULT '{}',  -- envelope-encrypted credential blob
    key_version INTEGER NOT NULL DEFAULT 1 REFERENCES encryption_keys(key_version),
    available_models JSONB NOT NULL DEFAULT '[]',
    last_test_status TEXT NOT NULL DEFAULT 'untested',  -- 'ok' | 'failed' | 'untested'
    last_test_at TIMESTAMPTZ,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_default_llm
    ON llm_providers (is_default) WHERE is_default = TRUE;
