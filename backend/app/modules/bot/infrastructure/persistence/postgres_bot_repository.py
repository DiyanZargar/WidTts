import uuid
from typing import Optional, List, Dict, Any
from app.shared.database.db import get_connection, get_transaction
from app.modules.bot.domain.interfaces.bot_repository_interface import BotRepositoryInterface


class PostgresBotRepository(BotRepositoryInterface):

    async def create(self, bot: Dict[str, Any]) -> str:
        bid = bot.get("id", str(uuid.uuid4()))
        async with get_connection() as conn:
            await conn.execute(
                """INSERT INTO bots (id, name, description, personality, system_prompt,
                   llm_provider_id, llm_model, stt_provider_id, tts_provider_id, is_active)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                bid, bot["name"], bot.get("description", ""),
                bot.get("personality", ""), bot.get("system_prompt", ""),
                bot.get("llm_provider_id"), bot.get("llm_model", ""),
                bot.get("stt_provider_id"), bot.get("tts_provider_id"),
                bot.get("is_active", False),
            )
        return bid

    async def get_by_id(self, bot_id: str) -> Optional[Dict[str, Any]]:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM bots WHERE id = $1", bot_id)
            return dict(row) if row else None

    async def list_all(self) -> List[Dict[str, Any]]:
        async with get_connection() as conn:
            rows = await conn.fetch("SELECT * FROM bots ORDER BY created_at DESC")
            return [dict(r) for r in rows]

    async def update(self, bot_id: str, updates: Dict[str, Any]) -> None:
        sets = []
        vals = []
        idx = 1
        for key in ("name", "description", "personality", "system_prompt",
                     "llm_provider_id", "llm_model", "stt_provider_id", "tts_provider_id", "is_active"):
            if key in updates:
                sets.append(f"{key} = ${idx}")
                vals.append(updates[key])
                idx += 1
        if not sets:
            return
        sets.append("updated_at = NOW()")
        vals.append(bot_id)
        sql = f"UPDATE bots SET {', '.join(sets)} WHERE id = ${idx}"
        async with get_connection() as conn:
            await conn.execute(sql, *vals)

    async def delete(self, bot_id: str) -> None:
        async with get_connection() as conn:
            await conn.execute("DELETE FROM bots WHERE id = $1", bot_id)

    async def get_active(self) -> Optional[Dict[str, Any]]:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM bots WHERE is_active = TRUE")
            return dict(row) if row else None

    async def activate(self, bot_id: str) -> None:
        """Atomically deactivate all bots, then activate the target."""
        async with get_transaction() as conn:
            await conn.execute("UPDATE bots SET is_active = FALSE WHERE is_active = TRUE")
            await conn.execute(
                "UPDATE bots SET is_active = TRUE, updated_at = NOW() WHERE id = $1",
                bot_id,
            )
