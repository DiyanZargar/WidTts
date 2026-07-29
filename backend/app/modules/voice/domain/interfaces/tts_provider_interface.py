from abc import ABC, abstractmethod


class TTSProviderInterface(ABC):

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """REST-style single-block synthesis."""
        raise NotImplementedError

    @abstractmethod
    async def synthesize_stream(self, text: str):
        """Streaming synthesis yielding audio chunks as they arrive."""
        raise NotImplementedError

    @abstractmethod
    async def connect_stream(self) -> None:
        """Open a persistent streaming TTS connection (one per conversation)."""
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        """Close any open connections and release resources."""
        raise NotImplementedError