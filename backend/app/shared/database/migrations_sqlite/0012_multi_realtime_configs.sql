-- Add name, provider_type, is_active columns to realtime_runtime_config
-- SQLite supports ALTER TABLE ADD COLUMN

ALTER TABLE realtime_runtime_config ADD COLUMN name TEXT NOT NULL DEFAULT 'Default Transport';
ALTER TABLE realtime_runtime_config ADD COLUMN provider_type TEXT NOT NULL DEFAULT 'livekit';
ALTER TABLE realtime_runtime_config ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1;
