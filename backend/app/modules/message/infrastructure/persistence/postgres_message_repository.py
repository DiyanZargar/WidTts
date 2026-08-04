from typing import List, Dict, Any
from app.shared.database.db import get_connection
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface


class PostgresMessageRepository(MessageRepositoryInterface):

    async def add(self, session_id: str, sender: str, text: str) -> None:
        async with get_connection() as conn:
            await conn.execute(
                "INSERT INTO messages (session_id, sender, text) VALUES ($1, $2, $3)",
                session_id, sender, text,
            )

    async def get_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        async with get_connection() as conn:
            rows = await conn.fetch(
                "SELECT sender, text, created_at FROM messages WHERE session_id=$1 ORDER BY id ASC",
                session_id,
            )
            return [dict(r) for r in rows]
