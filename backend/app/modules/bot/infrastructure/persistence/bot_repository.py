import uuid
import json
from typing import Optional, List, Dict, Any
from app.shared.database.db import get_connection, get_transaction
from app.modules.bot.domain.interfaces.bot_repository_interface import BotRepositoryInterface


class BotRepository(BotRepositoryInterface):
    """Generic repository for managing bots in the database."""

    async def create(self, bot: Dict[str, Any]) -> str:
        bid = bot.get("id", str(uuid.uuid4()))
        async with get_connection() as conn:
            await conn.execute(
                """INSERT INTO bots (id, name, description, personality, system_prompt,
                   llm_provider_id, llm_model, stt_provider_id, tts_provider_id,
                   stt_model, tts_model, stt_languages, stt_primary_language,
                   tts_languages, tts_primary_language, greeting,
                   tts_custom_model, tts_custom_voice_id, tts_custom_endpoint, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                bid, bot["name"], bot.get("description", ""),
                bot.get("personality", ""), bot.get("system_prompt", ""),
                bot.get("llm_provider_id"), bot.get("llm_model", ""),
                bot.get("stt_provider_id"), bot.get("tts_provider_id"),
                bot.get("stt_model", ""), bot.get("tts_model", ""),
                json.dumps(bot.get("stt_languages", ["en"])),
                bot.get("stt_primary_language", "en"),
                json.dumps(bot.get("tts_languages", ["en"])),
                bot.get("tts_primary_language", "en"),
                bot.get("greeting", ""),
                bot.get("tts_custom_model", ""),
                bot.get("tts_custom_voice_id", ""),
                bot.get("tts_custom_endpoint", ""),
                bot.get("is_active", False),
            )
        return bid

    async def get_by_id(self, bot_id: str) -> Optional[Dict[str, Any]]:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM bots WHERE id = ?", bot_id)
            return _deserialize_row(row) if row else None

    async def list_all(self) -> List[Dict[str, Any]]:
        async with get_connection() as conn:
            rows = await conn.fetch("SELECT * FROM bots ORDER BY created_at DESC")
            return [_deserialize_row(r) for r in rows]

    async def update(self, bot_id: str, updates: Dict[str, Any]) -> None:
        sets = []
        vals = []
        scalar_keys = [
            "name", "description", "personality", "system_prompt",
            "llm_provider_id", "llm_model", "stt_provider_id", "tts_provider_id",
            "stt_model", "tts_model", "stt_primary_language", "tts_primary_language",
            "greeting", "tts_custom_model", "tts_custom_voice_id", "tts_custom_endpoint", "is_active",
        ]
        json_keys = ["stt_languages", "tts_languages"]

        for key in scalar_keys:
            if key in updates:
                sets.append(f"{key} = ?")
                vals.append(updates[key])
        for key in json_keys:
            if key in updates:
                val = updates[key]
                sets.append(f"{key} = ?")
                vals.append(json.dumps(val) if isinstance(val, list) else val)

        if not sets:
            return
        sets.append("updated_at = datetime('now')")
        vals.append(bot_id)
        sql = f"UPDATE bots SET {', '.join(sets)} WHERE id = ?"
        async with get_connection() as conn:
            await conn.execute(sql, *vals)

    async def delete(self, bot_id: str) -> None:
        async with get_connection() as conn:
            await conn.execute("DELETE FROM bots WHERE id = ?", bot_id)

    async def get_active(self) -> Optional[Dict[str, Any]]:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM bots WHERE is_active = 1")
            return _deserialize_row(row) if row else None

    async def activate(self, bot_id: str) -> None:
        async with get_transaction() as conn:
            await conn.execute("UPDATE bots SET is_active = 0 WHERE is_active = 1")
            await conn.execute(
                "UPDATE bots SET is_active = 1, updated_at = datetime('now') WHERE id = ?",
                bot_id,
            )

    async def deploy(self, bot_id: str, slug: str) -> None:
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE bots SET deploy_slug = ?, is_deployed = 1, updated_at = datetime('now') WHERE id = ?",
                slug, bot_id,
            )

    async def undeploy(self, bot_id: str) -> None:
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE bots SET deploy_slug = NULL, is_deployed = 0, updated_at = datetime('now') WHERE id = ?",
                bot_id,
            )

    async def slug_exists(self, slug: str, exclude_bot_id: Optional[str] = None) -> bool:
        async with get_connection() as conn:
            if exclude_bot_id:
                row = await conn.fetchrow(
                    "SELECT 1 FROM bots WHERE deploy_slug = ? AND is_deployed = 1 AND id != ?",
                    slug, exclude_bot_id,
                )
            else:
                row = await conn.fetchrow(
                    "SELECT 1 FROM bots WHERE deploy_slug = ? AND is_deployed = 1",
                    slug,
                )
            return row is not None

    async def get_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM bots WHERE deploy_slug = ? AND is_deployed = 1",
                slug,
            )
            return _deserialize_row(row) if row else None


# Backward-compatible alias
PostgresBotRepository = BotRepository


def _deserialize_row(row) -> Dict[str, Any]:
    d = dict(row)
    for key in ("stt_languages", "tts_languages"):
        val = d.get(key)
        if isinstance(val, str):
            try:
                d[key] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                d[key] = ["en"]
        elif not isinstance(val, list):
            d[key] = ["en"]
    return d
