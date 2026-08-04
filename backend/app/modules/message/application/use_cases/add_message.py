from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface


class AddMessage:

    def __init__(self, message_repository: MessageRepositoryInterface):
        self._message_repository = message_repository

    async def execute(self, session_id: str, sender: str, text: str) -> None:
        await self._message_repository.add(session_id, sender, text)
