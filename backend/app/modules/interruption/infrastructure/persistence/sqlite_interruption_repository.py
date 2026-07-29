from datetime import datetime, timezone
from app.shared.database.db import get_connection
from app.modules.interruption.domain.interfaces.interruption_repository_interface import (
    InterruptionRepositoryInterface,
)


class SqliteInterruptionRepository(InterruptionRepositoryInterface):

    def add(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO interruptions (session_id, interruption_type, interruption_text, timestamp) VALUES (?, ?, ?, ?)",
                (session_id, interruption_type, interruption_text, datetime.now(timezone.utc).isoformat()),
            )
