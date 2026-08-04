-- Encryption keys table for envelope encryption
CREATE TABLE IF NOT EXISTS encryption_keys (
    key_version SERIAL PRIMARY KEY,
    wrapped_dek BYTEA NOT NULL,
    nonce BYTEA NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Only one key can be active
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_key
    ON encryption_keys (is_active) WHERE is_active = TRUE;
