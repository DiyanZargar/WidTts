"""
Provider Health Manager — provider-independent health monitoring, circuit breaker, and retry policy.
"""
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
import logging

from app.shared.config.runtime_limits import get_limits

logger = logging.getLogger("provider_health")


class CircuitState(str, Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Provider is failing, reject calls
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class ProviderStats:
    name: str
    total_requests: int = 0
    total_failures: int = 0
    total_successes: int = 0
    consecutive_failures: int = 0
    last_success_at: float = 0.0
    last_failure_at: float = 0.0
    last_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    circuit_state: CircuitState = CircuitState.CLOSED
    circuit_opened_at: float = 0.0


class ProviderHealthManager:
    """Monitors provider health with circuit breaker and latency tracking."""

    def __init__(self):
        self._providers: Dict[str, ProviderStats] = {}
        self._limits = get_limits()

    def register(self, name: str) -> None:
        self._providers[name] = ProviderStats(name=name)
        logger.info(f"[PROVIDER_HEALTH] Registered provider: {name}")

    def record_success(self, name: str, latency_ms: float = 0.0) -> None:
        stats = self._providers.get(name)
        if not stats:
            return
        stats.total_requests += 1
        stats.total_successes += 1
        stats.consecutive_failures = 0
        stats.last_success_at = time.time()
        stats.last_latency_ms = latency_ms
        # Exponential moving average
        if stats.avg_latency_ms == 0:
            stats.avg_latency_ms = latency_ms
        else:
            stats.avg_latency_ms = stats.avg_latency_ms * 0.8 + latency_ms * 0.2

        if stats.circuit_state == CircuitState.HALF_OPEN:
            stats.circuit_state = CircuitState.CLOSED
            logger.info(f"[PROVIDER_HEALTH] Circuit CLOSED for {name}")

    def record_failure(self, name: str, error: str = "") -> None:
        stats = self._providers.get(name)
        if not stats:
            return
        stats.total_requests += 1
        stats.total_failures += 1
        stats.consecutive_failures += 1
        stats.last_failure_at = time.time()

        threshold = self._limits.circuit_breaker_threshold
        if stats.consecutive_failures >= threshold and stats.circuit_state == CircuitState.CLOSED:
            stats.circuit_state = CircuitState.OPEN
            stats.circuit_opened_at = time.time()
            logger.warning(f"[PROVIDER_HEALTH] Circuit OPEN for {name} after {stats.consecutive_failures} failures")

    def is_available(self, name: str) -> bool:
        stats = self._providers.get(name)
        if not stats:
            return True

        if stats.circuit_state == CircuitState.CLOSED:
            return True

        if stats.circuit_state == CircuitState.OPEN:
            elapsed = time.time() - stats.circuit_opened_at
            if elapsed >= self._limits.circuit_breaker_reset_seconds:
                stats.circuit_state = CircuitState.HALF_OPEN
                logger.info(f"[PROVIDER_HEALTH] Circuit HALF_OPEN for {name}")
                return True
            return False

        return True  # HALF_OPEN allows one request

    def get_stats(self, name: str) -> Dict[str, Any]:
        stats = self._providers.get(name)
        if not stats:
            return {"name": name, "registered": False}
        return {
            "name": stats.name,
            "total_requests": stats.total_requests,
            "total_failures": stats.total_failures,
            "total_successes": stats.total_successes,
            "consecutive_failures": stats.consecutive_failures,
            "last_latency_ms": round(stats.last_latency_ms, 1),
            "avg_latency_ms": round(stats.avg_latency_ms, 1),
            "circuit_state": stats.circuit_state.value,
            "success_rate": round(stats.total_successes / max(stats.total_requests, 1), 3),
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        return {name: self.get_stats(name) for name in self._providers}
