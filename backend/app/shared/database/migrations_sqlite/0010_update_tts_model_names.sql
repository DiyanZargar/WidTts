-- Migration 0010: Update Deepgram TTS model identifiers
UPDATE speech_providers
SET tts_model = REPLACE(tts_model, 'aura-2-', 'aura-')
WHERE tts_model LIKE 'aura-2-%';
