from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class BotRepositoryInterface(ABC):

    @abstractmethod
    async def create(self, bot: Dict[str, Any]) -> str:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, bot_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def list_all(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def update(self, bot_id: str, updates: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def delete(self, bot_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_active(self) -> Optional[Dict[str, Any]]:
        """Get the currently active bot (is_active=true)."""
        raise NotImplementedError

    @abstractmethod
    async def activate(self, bot_id: str) -> None:
        """
        Set the given bot as active and deactivate all others.
        Enforced by partial unique index idx_one_active_bot.
        """
        raise NotImplementedError

    @abstractmethod
    async def deploy(self, bot_id: str, slug: str) -> None:
        """Deploy a bot with a unique URL slug."""
        raise NotImplementedError

    @abstractmethod
    async def undeploy(self, bot_id: str) -> None:
        """Remove a bot's deployment (clear slug + is_deployed)."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get a deployed bot by its URL slug."""
        raise NotImplementedError
