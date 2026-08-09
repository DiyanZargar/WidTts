-- Split single speech_provider_id into separate STT and TTS provider references.
-- Existing speech_provider_id data is migrated to both new columns.

ALTER TABLE bots
    ADD COLUMN stt_provider_id TEXT REFERENCES speech_providers(id) ON DELETE SET NULL,
    ADD COLUMN tts_provider_id TEXT REFERENCES speech_providers(id) ON DELETE SET NULL;

-- Migrate existing data: copy speech_provider_id to both new columns
UPDATE bots SET
    stt_provider_id = speech_provider_id,
    tts_provider_id = speech_provider_id
WHERE speech_provider_id IS NOT NULL;

-- Drop the old column
ALTER TABLE bots DROP COLUMN speech_provider_id;
