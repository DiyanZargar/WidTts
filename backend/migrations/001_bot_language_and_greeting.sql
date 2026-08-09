-- Migration 001: Bot language columns + greeting
-- Date: 2026-08-09
-- Description: Adds per-bot STT/TTS language configuration and greeting field

-- Per-bot language configuration (TEXT columns storing JSON arrays)
ALTER TABLE bots ADD COLUMN IF NOT EXISTS stt_languages TEXT DEFAULT '["en"]';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS stt_primary_language TEXT DEFAULT 'en';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS tts_languages TEXT DEFAULT '["en"]';
ALTER TABLE bots ADD COLUMN IF NOT EXISTS tts_primary_language TEXT DEFAULT 'en';

-- Bot greeting field (optional, used by LLM to generate greeting)
ALTER TABLE bots ADD COLUMN IF NOT EXISTS greeting TEXT DEFAULT '';
