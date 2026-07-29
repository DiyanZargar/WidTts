from typing import Optional, Dict, Any
from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface


class GetSession:

    def __init__(self, session_repository: SessionRepositoryInterface):
        self._session_repository = session_repository

    def execute(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._session_repository.get_by_id(session_id)
