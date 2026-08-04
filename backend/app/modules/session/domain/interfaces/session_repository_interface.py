from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class SessionRepositoryInterface(ABC):

    @abstractmethod
    async def create(self, session_id: str, conversation_type: str, user_id: str = "anonymous", bot_id: str = None) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def update_pointer(self, session_id: str, index: int, state: str, retries: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def pause(self, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def close(self, session_id: str, status: str) -> None:
        raise NotImplementedError
