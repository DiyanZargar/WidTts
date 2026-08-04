from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class CreateSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    async def execute(self, session_id: str, conversation_type: str, user_id: str = "anonymous", bot_id: str = None) -> None:
        await self._session_repository.create(session_id, conversation_type, user_id, bot_id=bot_id)
