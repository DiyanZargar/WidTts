"""
Realtime Runtime Configuration Repository.

Manages realtime_runtime_config records in SQLite.
Supports multiple realtime configurations (Local Docker, Cloud, etc.)
with active selection and envelope-encrypted credentials.
"""

import logging
import uuid
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from app.shared.database.db import get_connection, get_transaction

logger = logging.getLogger("realtime_config_repo")


def _format_row(row) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    result = dict(row)
    result["id"] = str(result["id"])
    for key in ("encrypted_api_key", "encrypted_api_secret"):
        val = result.get(key)
        if isinstance(val, str):
            try:
                result[key] = json.loads(val)
            except Exception:
                pass
    return result


class RealtimeConfigRepository:
    """Repository for the realtime_runtime_config table."""

    async def get_all(self) -> List[Dict[str, Any]]:
        """Return all realtime configuration records."""
        async with get_connection() as conn:
            rows = await conn.fetch(
                "SELECT * FROM realtime_runtime_config ORDER BY is_active DESC, updated_at DESC"
            )
            return [_format_row(r) for r in rows]

    async def get_active(self) -> Optional[Dict[str, Any]]:
        """Return the currently active config row, or fallback to environment configuration (.env)."""
        try:
            async with get_connection() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM realtime_runtime_config WHERE is_active = 1 ORDER BY updated_at DESC LIMIT 1"
                )
                if not row:
                    row = await conn.fetchrow(
                        "SELECT * FROM realtime_runtime_config ORDER BY updated_at DESC LIMIT 1"
                    )
                if row:
                    return _format_row(row)
        except Exception as e:
            logger.warning(f"Failed to fetch realtime config from DB: {e}")

        # Fallback to environment configuration (.env)
        from app.shared.config.settings import settings
        from app.shared.security.envelope_encryption import encrypt_and_store

        enc_key, _ = await encrypt_and_store({"value": settings.livekit_api_key})
        enc_secret, _ = await encrypt_and_store({"value": settings.livekit_api_secret})

        return {
            "id": "00000000-0000-0000-0000-000000000000",
            "name": "Environment Transport",
            "provider_type": "livekit",
            "server_url": settings.livekit_url,
            "encrypted_api_key": enc_key,
            "encrypted_api_secret": enc_secret,
            "room_token_ttl_seconds": settings.livekit_token_ttl_seconds,
            "audio_sample_rate": settings.livekit_audio_sample_rate,
            "is_active": True,
        }

    async def get_by_id(self, config_id: str) -> Optional[Dict[str, Any]]:
        """Return a single config by ID."""
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM realtime_runtime_config WHERE id = ?",
                config_id,
            )
            return _format_row(row)

    async def create(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new realtime config record."""
        config_id = str(uuid.uuid4())
        async with get_transaction() as conn:
            # If this is the first config or set as active, deactivate others
            is_active = config.get("is_active", True)
            if is_active:
                await conn.execute("UPDATE realtime_runtime_config SET is_active = 0")

            await conn.execute(
                """
                INSERT INTO realtime_runtime_config
                    (id, name, provider_type, server_url, encrypted_api_key, encrypted_api_secret,
                     room_token_ttl_seconds, audio_sample_rate, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                config_id,
                config.get("name", "Realtime Provider"),
                config.get("provider_type", "livekit"),
                config["server_url"],
                json.dumps(config["encrypted_api_key"]),
                json.dumps(config["encrypted_api_secret"]),
                config.get("room_token_ttl_seconds", 3600),
                config.get("audio_sample_rate", 16000),
                is_active,
            )
            # Fetch the created row
            row = await conn.fetchrow("SELECT * FROM realtime_runtime_config WHERE id = ?", config_id)
            return _format_row(row)

    async def update(self, config_id: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an existing realtime config record."""
        async with get_transaction() as conn:
            now = datetime.now(timezone.utc).isoformat()
            fields = []
            values = []

            if "name" in config:
                fields.append("name = ?")
                values.append(config["name"])
            if "provider_type" in config:
                fields.append("provider_type = ?")
                values.append(config["provider_type"])
            if "server_url" in config:
                fields.append("server_url = ?")
                values.append(config["server_url"])
            if "encrypted_api_key" in config:
                fields.append("encrypted_api_key = ?")
                values.append(json.dumps(config["encrypted_api_key"]))
            if "encrypted_api_secret" in config:
                fields.append("encrypted_api_secret = ?")
                values.append(json.dumps(config["encrypted_api_secret"]))
            if "room_token_ttl_seconds" in config:
                fields.append("room_token_ttl_seconds = ?")
                values.append(config["room_token_ttl_seconds"])
            if "audio_sample_rate" in config:
                fields.append("audio_sample_rate = ?")
                values.append(config["audio_sample_rate"])

            fields.append("updated_at = ?")
            values.append(now)

            values.append(config_id)
            query = f"UPDATE realtime_runtime_config SET {', '.join(fields)} WHERE id = ?"
            await conn.execute(query, *values)
            row = await conn.fetchrow("SELECT * FROM realtime_runtime_config WHERE id = ?", config_id)
            return _format_row(row)

    async def set_active(self, config_id: str) -> Optional[Dict[str, Any]]:
        """Mark the specified config as active and deactivate all others."""
        async with get_transaction() as conn:
            await conn.execute("UPDATE realtime_runtime_config SET is_active = 0")
            await conn.execute(
                "UPDATE realtime_runtime_config SET is_active = 1, updated_at = datetime('now') WHERE id = ?",
                config_id,
            )
            row = await conn.fetchrow("SELECT * FROM realtime_runtime_config WHERE id = ?", config_id)
            return _format_row(row)

    async def delete(self, config_id: str) -> bool:
        """Delete a realtime config record by ID."""
        async with get_transaction() as conn:
            await conn.execute(
                "DELETE FROM realtime_runtime_config WHERE id = ?",
                config_id,
            )
            # If deleted provider was active, make another active if available
            row = await conn.fetchrow("SELECT id FROM realtime_runtime_config WHERE is_active = 1 LIMIT 1")
            if not row:
                await conn.execute(
                    "UPDATE realtime_runtime_config SET is_active = 1 WHERE id = (SELECT id FROM realtime_runtime_config ORDER BY updated_at DESC LIMIT 1)"
                )
            return True

    async def update_test_status(
        self, config_id: str, status: str, error: Optional[str] = None
    ) -> None:
        """Update test status for a given config_id."""
        async with get_connection() as conn:
            now = datetime.now(timezone.utc).isoformat()
            await conn.execute(
                """
                UPDATE realtime_runtime_config SET
                    last_tested_at = ?,
                    last_test_status = ?,
                    last_test_error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                now,
                status,
                error,
                now,
                config_id,
            )
