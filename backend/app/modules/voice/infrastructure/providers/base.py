"""Base speech provider contract and shared utilities.

Every speech provider (Deepgram, ElevenLabs, Fish Audio, future engines)
must implement ``BaseSpeechProvider`` so the factory dispatcher can
delegate uniformly without if/elif branching.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

logger = logging.getLogger("speech_provider")


# ── Error types ──────────────────────────────────────────────────────

class UnsupportedProviderError(Exception):
    """Raised when the factory encounters an unknown provider_type."""


# ── Credential helpers ───────────────────────────────────────────────

def mask(value: str, visible: int = 4) -> str:
    """Return a masked version of a secret for safe logging."""
    if not value or len(value) <= visible:
        return "****"
    return f"{value[:visible]}…(len={len(value)})"


def mask_credentials(creds: Dict[str, Any]) -> Dict[str, str]:
    """Return a copy of creds with all values masked for logging."""
    return {k: mask(str(v)) for k, v in creds.items()}


# ── Abstract base ────────────────────────────────────────────────────

class BaseSpeechProvider(ABC):
    """Universal base provider contract for speech engines.

    Each concrete provider maps a generic ``config`` dict (row from the
    ``speech_providers`` table) and decrypted ``creds`` dict into a
    LiveKit-compatible STT or TTS plugin instance.
    """

    @abstractmethod
    def build_stt(self, config: Dict[str, Any], creds: Dict[str, Any]) -> Any:
        """Construct a LiveKit-compatible STT instance.

        Parameters
        ----------
        config : dict
            Speech provider row from the database.
        creds : dict
            Decrypted credentials (e.g. ``{"api_key": "sk-..."}``).

        Returns
        -------
        A livekit STT plugin instance.
        """
        raise NotImplementedError

    @abstractmethod
    def build_tts(self, config: Dict[str, Any], creds: Dict[str, Any]) -> Any:
        """Construct a LiveKit-compatible TTS instance.

        Parameters
        ----------
        config : dict
            Speech provider row from the database.
        creds : dict
            Decrypted credentials (e.g. ``{"api_key": "sk-..."}``).

        Returns
        -------
        A livekit TTS plugin instance.
        """
        raise NotImplementedError
