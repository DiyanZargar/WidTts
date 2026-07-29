from datetime import datetime, timezone
from typing import List, Dict, Any
from app.shared.database.db import get_connection
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface


class SqliteMessageRepository(MessageRepositoryInterface):

    def add(self, session_id: str, sender: str, text: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, sender, text, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, sender, text, datetime.now(timezone.utc).isoformat()),
            )

    def get_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT sender, text, timestamp FROM messages WHERE session_id=? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [dict(r) for r in rows]
