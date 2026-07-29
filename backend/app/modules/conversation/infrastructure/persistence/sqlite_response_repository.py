from app.shared.database.db import get_connection
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface


class SqliteResponseRepository(ResponseRepositoryInterface):

    def add(self, sequence: int, session_id: str, user_response: str, validation_result: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO responses (sequence, session_id, user_response, validation_result) VALUES (?, ?, ?, ?)",
                (sequence, session_id, user_response, validation_result),
            )
