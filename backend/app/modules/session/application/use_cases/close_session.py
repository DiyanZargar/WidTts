from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class CloseSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, status: str) -> None:
        self._session_repository.close(session_id, status)
