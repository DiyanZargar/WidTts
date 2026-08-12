-- Add name_locked flag to bots table.
-- Once a bot is saved for the first time, its name (and derived slug) cannot change.

ALTER TABLE bots
    ADD COLUMN name_locked BOOLEAN NOT NULL DEFAULT FALSE;

-- All existing bots already have their names set — mark them as locked
UPDATE bots SET name_locked = TRUE WHERE TRUE;
