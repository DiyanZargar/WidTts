"""
Envelope Encryption for provider credentials.

Architecture:
- A Master Key (MEK) from settings.master_encryption_key wraps/unwraps Data Encryption Keys (DEKs)
- Each DEK is a random 256-bit AES key, encrypted (wrapped) by the MEK
- Credentials are encrypted with the DEK using AES-256-GCM
- The wrapped DEK + nonce are stored in the `encryption_keys` table
- Credentials in `llm_providers` / `speech_providers` store:
  { "key_version": int, "nonce": base64, "ciphertext": base64 }
"""

import base64
import json
import os
import logging
from typing import Dict, Any, Optional, Tuple

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.shared.config.settings import settings

logger = logging.getLogger("envelope_encryption")

# ── Key Derivation ──

def _get_master_key() -> bytes:
    """Load the 32-byte master encryption key from settings."""
    raw = settings.master_encryption_key
    if not raw:
        raise ValueError(
            "MASTER_ENCRYPTION_KEY is not set. Generate with: "
            "python -c \"import os,base64; print(base64.b64encode(os.urandom(32)).decode())\""
        )
    key = base64.b64decode(raw)
    if len(key) != 32:
        raise ValueError(f"MASTER_ENCRYPTION_KEY must be 32 bytes (got {len(key)})")
    return key


# ── DEK Management ──

def generate_dek() -> bytes:
    """Generate a random 256-bit Data Encryption Key."""
    return os.urandom(32)


def wrap_dek(dek: bytes) -> Tuple[bytes, bytes]:
    """
    Wrap (encrypt) a DEK with the master key.
    Returns (wrapped_dek, nonce).
    """
    mek = _get_master_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(mek)
    wrapped = aesgcm.encrypt(nonce, dek, None)
    return wrapped, nonce


def unwrap_dek(wrapped_dek: bytes, nonce: bytes) -> bytes:
    """Unwrap (decrypt) a DEK using the master key."""
    mek = _get_master_key()
    aesgcm = AESGCM(mek)
    return aesgcm.decrypt(nonce, wrapped_dek, None)


# ── Credential Encryption/Decryption ──

def encrypt_credential(plaintext: Dict[str, Any], dek: bytes) -> Dict[str, str]:
    """
    Encrypt a credential dict with a DEK using AES-256-GCM.

    Returns a dict suitable for JSONB storage:
    { "nonce": base64, "ciphertext": base64 }
    """
    nonce = os.urandom(12)
    aesgcm = AESGCM(dek)
    plaintext_bytes = json.dumps(plaintext).encode("utf-8")
    ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, None)

    return {
        "nonce": base64.b64encode(nonce).decode(),
        "ciphertext": base64.b64encode(ciphertext).decode(),
    }


def decrypt_credential(blob: Dict[str, str], dek: bytes) -> Dict[str, Any]:
    """
    Decrypt a credential blob using the DEK.

    The blob must contain 'nonce' and 'ciphertext' as base64 strings.
    """
    nonce = base64.b64decode(blob["nonce"])
    ciphertext = base64.b64decode(blob["ciphertext"])
    aesgcm = AESGCM(dek)
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext_bytes.decode("utf-8"))


# ── Database Integration ──

async def bootstrap_encryption_key():
    """
    Ensure at least one encryption key exists in the database.
    Called at application startup.
    """
    from app.shared.database.db import get_connection

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT key_version FROM encryption_keys WHERE is_active = TRUE"
        )
        if row:
            logger.info(f"[ENCRYPTION] Active key_version={row['key_version']}")
            return row["key_version"]

        # Bootstrap: create first key
        dek = generate_dek()
        wrapped, nonce = wrap_dek(dek)

        key_version = await conn.fetchval(
            """INSERT INTO encryption_keys (wrapped_dek, nonce, is_active)
               VALUES ($1, $2, TRUE)
               RETURNING key_version""",
            wrapped, nonce,
        )
        logger.info(f"[ENCRYPTION] Bootstrapped key_version={key_version}")
        return key_version


async def get_active_dek() -> Tuple[bytes, int]:
    """
    Load and unwrap the currently active DEK.
    Returns (dek_bytes, key_version).
    """
    from app.shared.database.db import get_connection

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT key_version, wrapped_dek, nonce FROM encryption_keys WHERE is_active = TRUE"
        )
        if not row:
            raise RuntimeError("No active encryption key found. Run bootstrap_encryption_key() first.")

        dek = unwrap_dek(bytes(row["wrapped_dek"]), bytes(row["nonce"]))
        return dek, row["key_version"]


async def encrypt_and_store(plaintext_creds: Dict[str, Any]) -> Tuple[Dict[str, str], int]:
    """
    Encrypt credentials using the active DEK.
    Returns (encrypted_blob, key_version) ready for DB storage.
    """
    dek, key_version = await get_active_dek()
    blob = encrypt_credential(plaintext_creds, dek)
    return blob, key_version


async def load_and_decrypt(credentials_enc: Dict[str, str], key_version: int) -> Dict[str, Any]:
    """
    Load the DEK for the given key_version and decrypt credentials.
    """
    from app.shared.database.db import get_connection

    async with get_connection() as conn:
        row = await conn.fetchrow(
            "SELECT wrapped_dek, nonce FROM encryption_keys WHERE key_version = $1",
            key_version,
        )
        if not row:
            raise RuntimeError(f"Encryption key_version={key_version} not found")

        dek = unwrap_dek(bytes(row["wrapped_dek"]), bytes(row["nonce"]))
        return decrypt_credential(credentials_enc, dek)
