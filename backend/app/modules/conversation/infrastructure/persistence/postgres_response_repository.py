import json
from app.shared.database.db import get_connection
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface


class PostgresResponseRepository(ResponseRepositoryInterface):

    async def add(self, sequence: int, session_id: str, user_response: str, validation_result: str) -> None:
        async with get_connection() as conn:
            await conn.execute(
                """INSERT INTO responses (session_id, question_id, transcript, classification, metadata)
                   VALUES ($1, $2, $3, $4, $5)""",
                session_id, str(sequence), user_response, "recorded",
                json.dumps({"raw_validation": validation_result}),
            )
