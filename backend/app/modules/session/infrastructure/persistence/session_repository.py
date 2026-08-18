from typing import Optional, Dict, Any
from app.shared.database.db import get_connection
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class SessionRepository(SessionRepositoryInterface):
    """Generic repository for managing voice sessions in the database."""

    async def create(self, session_id: str, conversation_type: str, user_id: str = "anonymous", bot_id: Optional[str] = None) -> None:
        async with get_connection() as conn:
            await conn.execute(
                """INSERT INTO sessions (id, user_id, conversation_type, bot_id, status, created_at)
                   VALUES (?, ?, ?, ?, 'active', datetime('now'))""",
                session_id, user_id, conversation_type, bot_id,
            )

    async def get_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sessions WHERE id = ?", session_id
            )
            return dict(row) if row else None

    async def close(self, session_id: str, status: str) -> None:
        async with get_connection() as conn:
            await conn.execute(
                """UPDATE sessions SET status=?, closed_at=datetime('now'), current_state='completed',
                   updated_at=datetime('now') WHERE id=?""",
                status, session_id,
            )

    async def close_active_for_user_bot(self, user_id: str, bot_id: str) -> None:
        """Close any lingering active sessions for this user+bot pair."""
        async with get_connection() as conn:
            await conn.execute(
                """UPDATE sessions SET status='completed', closed_at=datetime('now'),
                   updated_at=datetime('now') WHERE user_id=? AND bot_id=? AND status='active'""",
                user_id, bot_id,
            )
