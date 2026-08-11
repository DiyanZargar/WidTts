-- Add bot greeting field.
-- The greeting is spoken by the LLM at session start.

ALTER TABLE bots ADD COLUMN IF NOT EXISTS greeting TEXT DEFAULT '';
