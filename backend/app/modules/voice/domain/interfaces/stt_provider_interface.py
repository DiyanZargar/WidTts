from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class STTProviderInterface(ABC):

    @abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_audio(self, chunk: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    async def receive_any(self) -> Dict[str, Any]:
        """Receive raw parsed response message from STT provider."""
        raise NotImplementedError

    @abstractmethod
    async def receive_transcript(self) -> Optional[str]:
        """Receive only finalized transcripts."""
        raise NotImplementedError

    @abstractmethod
    async def drain_pending(self) -> None:
        """Discard all pending STT messages (used after TTS playback)."""
        raise NotImplementedError

    @abstractmethod
    def advance_epoch(self) -> int:
        """Increment the epoch counter and return the new value."""
        raise NotImplementedError

    @abstractmethod
    async def drain_before(self, epoch: int) -> int:
        """Drain only items older than the given epoch, keeping current items."""
        raise NotImplementedError

    @abstractmethod
    def parse_stt_message(self, raw: dict) -> tuple:
        """
        Extract transcript text and finality flag from a raw STT message.
        Returns (text: str, is_final: bool).
        """
        raise NotImplementedError

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
