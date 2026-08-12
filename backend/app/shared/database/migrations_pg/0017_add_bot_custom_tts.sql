-- Add custom TTS fields for providers that support custom models/voices/endpoints.
-- Used by Fish Audio (custom voice profiles) and other custom TTS providers.

ALTER TABLE bots
    ADD COLUMN tts_custom_model TEXT NOT NULL DEFAULT '',
    ADD COLUMN tts_custom_voice_id TEXT NOT NULL DEFAULT '',
    ADD COLUMN tts_custom_endpoint TEXT NOT NULL DEFAULT '';
