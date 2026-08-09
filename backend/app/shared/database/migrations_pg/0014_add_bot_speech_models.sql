-- Add per-bot speech model and language configuration.
-- Model and language selection moves from speech_providers to bots,
-- so each bot can independently choose models/languages from its provider.
-- Languages are configured per-section (STT and TTS separately).

ALTER TABLE bots
    ADD COLUMN stt_model TEXT NOT NULL DEFAULT '',
    ADD COLUMN tts_model TEXT NOT NULL DEFAULT '',
    ADD COLUMN stt_languages JSONB NOT NULL DEFAULT '["en"]',
    ADD COLUMN stt_primary_language TEXT NOT NULL DEFAULT 'en',
    ADD COLUMN tts_languages JSONB NOT NULL DEFAULT '["en"]',
    ADD COLUMN tts_primary_language TEXT NOT NULL DEFAULT 'en';
