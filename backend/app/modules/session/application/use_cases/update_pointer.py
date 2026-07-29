from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class UpdatePointer:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str, index: int, state: str, retries: int) -> None:
        self._session_repository.update_pointer(session_id, index, state, retries)
