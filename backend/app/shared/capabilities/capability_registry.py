"""
Capability Registry — centralized feature detection.

Components query capabilities instead of using scattered feature checks.
"""
from typing import Dict, Set
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("capability_registry")


@dataclass
class Capability:
    name: str
    available: bool = False
    version: str = ""
    details: Dict[str, str] = field(default_factory=dict)


class CapabilityRegistry:
    """Tracks which features are available at runtime."""

    def __init__(self):
        self._capabilities: Dict[str, Capability] = {}

    def register(self, name: str, available: bool = True, version: str = "", **details) -> None:
        self._capabilities[name] = Capability(
            name=name, available=available, version=version, details=details
        )
        status = "available" if available else "unavailable"
        logger.info(f"[CAPABILITY] Registered: {name} = {status}")

    def is_available(self, name: str) -> bool:
        cap = self._capabilities.get(name)
        return cap.available if cap else False

    def get(self, name: str) -> Capability:
        return self._capabilities.get(name, Capability(name=name))

    def list_available(self) -> Set[str]:
        return {name for name, cap in self._capabilities.items() if cap.available}

    def list_all(self) -> Dict[str, Dict]:
        return {
            name: {"available": cap.available, "version": cap.version, "details": cap.details}
            for name, cap in self._capabilities.items()
        }

    def snapshot(self) -> Dict[str, bool]:
        return {name: cap.available for name, cap in self._capabilities.items()}
