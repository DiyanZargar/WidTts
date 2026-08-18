-- Add name_locked flag to bots table.
ALTER TABLE bots ADD COLUMN name_locked INTEGER NOT NULL DEFAULT 0;

-- All existing bots already have their names set — mark them as locked
UPDATE bots SET name_locked = 1 WHERE 1;
