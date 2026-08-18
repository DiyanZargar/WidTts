from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class SpeechProviderRepositoryInterface(ABC):

    @abstractmethod
    async def create(self, provider: Dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def update(self, provider_id: str, updates: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, provider_id: str) -> None:
        raise NotImplementedError
