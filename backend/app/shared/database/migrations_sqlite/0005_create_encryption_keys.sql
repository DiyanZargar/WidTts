-- Encryption keys table for envelope encryption (SQLite)
CREATE TABLE IF NOT EXISTS encryption_keys (
    key_version INTEGER PRIMARY KEY AUTOINCREMENT,
    wrapped_dek BLOB NOT NULL,
    nonce BLOB NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Only one key can be active (partial unique index, SQLite 3.8+)
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_key
    ON encryption_keys (is_active) WHERE is_active = 1;
