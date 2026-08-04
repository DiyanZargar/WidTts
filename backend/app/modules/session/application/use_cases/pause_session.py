from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class PauseSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    async def execute(self, session_id: str) -> None:
        await self._session_repository.pause(session_id)
