-- Add custom TTS fields.
ALTER TABLE bots ADD COLUMN tts_custom_model TEXT NOT NULL DEFAULT '';
ALTER TABLE bots ADD COLUMN tts_custom_voice_id TEXT NOT NULL DEFAULT '';
ALTER TABLE bots ADD COLUMN tts_custom_endpoint TEXT NOT NULL DEFAULT '';
