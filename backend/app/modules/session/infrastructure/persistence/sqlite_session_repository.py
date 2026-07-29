from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.shared.database.db import get_connection
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class SqliteSessionRepository(SessionRepositoryInterface):

    def create(self, session_id: str, conversation_type: str, user_id: str = "anonymous") -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, user_id, start_time, conversation_type, status) VALUES (?, ?, ?, ?, 'active')",
                (session_id, user_id, datetime.now(timezone.utc).isoformat(), conversation_type),
            )

    def get_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return dict(row) if row else None

    def update_pointer(self, session_id: str, index: int, state: str, retries: int) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET current_question_index=?, current_state=?, retries=?, status='active' WHERE session_id=?",
                (index, state, retries, session_id),
            )

    def pause(self, session_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET status='paused' WHERE session_id=? AND status='active'",
                (session_id,),
            )

    def close(self, session_id: str, status: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET status=?, end_time=?, current_state='completed' WHERE session_id=?",
                (status, datetime.now(timezone.utc).isoformat(), session_id),
            )
