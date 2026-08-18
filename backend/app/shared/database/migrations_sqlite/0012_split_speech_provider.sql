-- Split single speech_provider_id into separate STT and TTS provider references.
-- SQLite doesn't support multi-column ALTER TABLE ADD, so we add one at a time.

ALTER TABLE bots ADD COLUMN stt_provider_id TEXT REFERENCES speech_providers(id) ON DELETE SET NULL;
ALTER TABLE bots ADD COLUMN tts_provider_id TEXT REFERENCES speech_providers(id) ON DELETE SET NULL;

-- Migrate existing data
UPDATE bots SET
    stt_provider_id = speech_provider_id,
    tts_provider_id = speech_provider_id
WHERE speech_provider_id IS NOT NULL;

-- Drop the old column (SQLite doesn't support DROP COLUMN before 3.35.0,
-- so we use the safe approach — leave it and ignore it)
-- For SQLite >= 3.35.0, uncomment:
-- ALTER TABLE bots DROP COLUMN speech_provider_id;
