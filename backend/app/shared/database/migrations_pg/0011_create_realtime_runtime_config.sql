CREATE TABLE IF NOT EXISTS realtime_runtime_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    server_url TEXT NOT NULL,
    encrypted_api_key JSONB NOT NULL,
    encrypted_api_secret JSONB NOT NULL,
    room_token_ttl_seconds INT NOT NULL DEFAULT 3600,
    audio_sample_rate INT NOT NULL DEFAULT 16000,
    last_tested_at TIMESTAMPTZ,
    last_test_status TEXT,
    last_test_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
