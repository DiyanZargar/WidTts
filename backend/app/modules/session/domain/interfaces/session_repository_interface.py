from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class SessionRepositoryInterface(ABC):

    @abstractmethod
    def create(self, session_id: str, conversation_type: str, user_id: str = "anonymous") -> None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def update_pointer(self, session_id: str, index: int, state: str, retries: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def pause(self, session_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def close(self, session_id: str, status: str) -> None:
        raise NotImplementedError
