from abc import ABC, abstractmethod


class InterruptionRepositoryInterface(ABC):

    @abstractmethod
    async def add(self, session_id: str, interruption_type: str, interruption_text: str) -> None:
        raise NotImplementedError
