-- Add per-bot speech model and language configuration.
ALTER TABLE bots ADD COLUMN stt_model TEXT NOT NULL DEFAULT '';
ALTER TABLE bots ADD COLUMN tts_model TEXT NOT NULL DEFAULT '';
ALTER TABLE bots ADD COLUMN stt_languages TEXT NOT NULL DEFAULT '["en"]';
ALTER TABLE bots ADD COLUMN stt_primary_language TEXT NOT NULL DEFAULT 'en';
ALTER TABLE bots ADD COLUMN tts_languages TEXT NOT NULL DEFAULT '["en"]';
ALTER TABLE bots ADD COLUMN tts_primary_language TEXT NOT NULL DEFAULT 'en';
