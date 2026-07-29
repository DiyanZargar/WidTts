from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class ConversationRepositoryInterface(ABC):

    @abstractmethod
    def initialize(self) -> None:
        """Scan definitions directory, validate schema, verify uniqueness, and cache in memory."""
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a conversation definition from the in-memory cache."""
        raise NotImplementedError

    @abstractmethod
    def list_available(self) -> List[Dict[str, Any]]:
        """List metadata of all cached conversation packs."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, conversation_id: str) -> bool:
        """Check if a conversation ID exists in the cache."""
        raise NotImplementedError
