from typing import List, Dict, Any
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface


class GetMessages:

    def __init__(self, message_repository: MessageRepositoryInterface):
        self._message_repository = message_repository

    async def execute(self, session_id: str) -> List[Dict[str, Any]]:
        return await self._message_repository.get_by_session(session_id)
