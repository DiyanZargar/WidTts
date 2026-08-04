-- Speech providers table (STT + TTS)
CREATE TABLE IF NOT EXISTS speech_providers (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,  -- 'deepgram' | 'elevenlabs'
    credentials_enc JSONB NOT NULL DEFAULT '{}',  -- envelope-encrypted credential blob
    key_version INTEGER NOT NULL DEFAULT 1 REFERENCES encryption_keys(key_version),

    -- STT config
    stt_model TEXT NOT NULL DEFAULT '',
    stt_language TEXT NOT NULL DEFAULT 'en',
    stt_extra JSONB NOT NULL DEFAULT '{}',

    -- TTS config
    tts_model TEXT NOT NULL DEFAULT '',
    tts_voice_id TEXT NOT NULL DEFAULT '',
    tts_extra JSONB NOT NULL DEFAULT '{}',

    last_test_status TEXT NOT NULL DEFAULT 'untested',
    last_test_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
