from abc import ABC, abstractmethod
from typing import List, Dict, Any


class MessageRepositoryInterface(ABC):

    @abstractmethod
    async def add(self, session_id: str, sender: str, text: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        raise NotImplementedError
