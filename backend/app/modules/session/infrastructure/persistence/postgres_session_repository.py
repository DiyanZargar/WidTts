from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.shared.database.db import get_connection
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class PostgresSessionRepository(SessionRepositoryInterface):

    async def create(self, session_id: str, conversation_type: str, user_id: str = "anonymous", bot_id: str = None) -> None:
        async with get_connection() as conn:
            await conn.execute(
                """INSERT INTO sessions (id, user_id, conversation_type, bot_id, status, created_at)
                   VALUES ($1, $2, $3, $4, 'active', NOW())""",
                session_id, user_id, conversation_type, bot_id,
            )

    async def get_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        async with get_connection() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sessions WHERE id = $1", session_id
            )
            return dict(row) if row else None

    async def update_pointer(self, session_id: str, index: int, state: str, retries: int) -> None:
        async with get_connection() as conn:
            await conn.execute(
                """UPDATE sessions SET current_question_index=$1, current_state=$2, retries=$3,
                   status='active', updated_at=NOW() WHERE id=$4""",
                index, state, retries, session_id,
            )

    async def pause(self, session_id: str) -> None:
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE sessions SET status='paused', updated_at=NOW() WHERE id=$1 AND status='active'",
                session_id,
            )

    async def close(self, session_id: str, status: str) -> None:
        async with get_connection() as conn:
            await conn.execute(
                """UPDATE sessions SET status=$1, closed_at=NOW(), current_state='completed',
                   updated_at=NOW() WHERE id=$2""",
                status, session_id,
            )
