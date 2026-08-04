from app.shared.database.db import get_connection
from app.modules.interruption.domain.interfaces.interruption_repository_interface import (
    InterruptionRepositoryInterface,
)


class PostgresInterruptionRepository(InterruptionRepositoryInterface):

    async def add(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        async with get_connection() as conn:
            await conn.execute(
                """INSERT INTO interruptions (session_id, interrupt_type, transcript)
                   VALUES ($1, $2, $3)""",
                session_id, interruption_type, interruption_text,
            )
