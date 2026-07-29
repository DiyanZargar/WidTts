"""
Error Classification Framework — structured error categories with recovery strategies.

Categories:
  - Recoverable: reconnect, retry, timeout, temporary provider failure
  - Fatal: unsupported browser, microphone unavailable, invalid session
  - UserError: permission denied, network offline, invalid configuration
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger("error_classifier")


class ErrorCategory(str, Enum):
    RECOVERABLE = "recoverable"
    FATAL = "fatal"
    USER_ERROR = "user_error"


class ErrorSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecoveryAction(str, Enum):
    RETRY = "retry"
    RECONNECT = "reconnect"
    RESTART_SESSION = "restart_session"
    NOTIFY_USER = "notify_user"
    NONE = "none"


@dataclass
class ClassifiedError:
    category: ErrorCategory
    severity: ErrorSeverity
    recovery_action: RecoveryAction
    retryable: bool
    max_retries: int
    retry_delay_ms: int
    notify_frontend: bool
    cleanup_required: bool
    message: str
    details: Dict[str, Any]


# Known error patterns → classification
_ERROR_MAP: Dict[str, Dict[str, Any]] = {
    # Recoverable
    "timeout": {
        "category": ErrorCategory.RECOVERABLE, "severity": ErrorSeverity.MEDIUM,
        "recovery": RecoveryAction.RETRY, "retryable": True, "max_retries": 3,
        "retry_delay_ms": 1000, "notify": False, "cleanup": False,
    },
    "connection_lost": {
        "category": ErrorCategory.RECOVERABLE, "severity": ErrorSeverity.MEDIUM,
        "recovery": RecoveryAction.RECONNECT, "retryable": True, "max_retries": 5,
        "retry_delay_ms": 500, "notify": False, "cleanup": False,
    },
    "provider_unavailable": {
        "category": ErrorCategory.RECOVERABLE, "severity": ErrorSeverity.HIGH,
        "recovery": RecoveryAction.RECONNECT, "retryable": True, "max_retries": 3,
        "retry_delay_ms": 2000, "notify": False, "cleanup": False,
    },
    "queue_overflow": {
        "category": ErrorCategory.RECOVERABLE, "severity": ErrorSeverity.LOW,
        "recovery": RecoveryAction.RETRY, "retryable": True, "max_retries": 1,
        "retry_delay_ms": 0, "notify": False, "cleanup": True,
    },
    # Fatal
    "unsupported_browser": {
        "category": ErrorCategory.FATAL, "severity": ErrorSeverity.CRITICAL,
        "recovery": RecoveryAction.NOTIFY_USER, "retryable": False, "max_retries": 0,
        "retry_delay_ms": 0, "notify": True, "cleanup": True,
    },
    "microphone_unavailable": {
        "category": ErrorCategory.FATAL, "severity": ErrorSeverity.CRITICAL,
        "recovery": RecoveryAction.NOTIFY_USER, "retryable": False, "max_retries": 0,
        "retry_delay_ms": 0, "notify": True, "cleanup": True,
    },
    "invalid_session": {
        "category": ErrorCategory.FATAL, "severity": ErrorSeverity.HIGH,
        "recovery": RecoveryAction.RESTART_SESSION, "retryable": False, "max_retries": 0,
        "retry_delay_ms": 0, "notify": True, "cleanup": True,
    },
    "worklet_load_failed": {
        "category": ErrorCategory.FATAL, "severity": ErrorSeverity.HIGH,
        "recovery": RecoveryAction.RETRY, "retryable": True, "max_retries": 1,
        "retry_delay_ms": 0, "notify": False, "cleanup": False,
    },
    # User errors
    "permission_denied": {
        "category": ErrorCategory.USER_ERROR, "severity": ErrorSeverity.HIGH,
        "recovery": RecoveryAction.NOTIFY_USER, "retryable": False, "max_retries": 0,
        "retry_delay_ms": 0, "notify": True, "cleanup": True,
    },
    "network_offline": {
        "category": ErrorCategory.USER_ERROR, "severity": ErrorSeverity.HIGH,
        "recovery": RecoveryAction.RECONNECT, "retryable": True, "max_retries": 10,
        "retry_delay_ms": 3000, "notify": True, "cleanup": False,
    },
}


def classify_error(error_type: str, message: str = "", details: Optional[Dict] = None) -> ClassifiedError:
    """Classify an error by type string and return structured classification."""
    spec = _ERROR_MAP.get(error_type, {
        "category": ErrorCategory.RECOVERABLE, "severity": ErrorSeverity.MEDIUM,
        "recovery": RecoveryAction.RETRY, "retryable": True, "max_retries": 1,
        "retry_delay_ms": 1000, "notify": False, "cleanup": False,
    })

    classified = ClassifiedError(
        category=spec["category"],
        severity=spec["severity"],
        recovery_action=spec["recovery"],
        retryable=spec["retryable"],
        max_retries=spec["max_retries"],
        retry_delay_ms=spec["retry_delay_ms"],
        notify_frontend=spec["notify"],
        cleanup_required=spec["cleanup"],
        message=message or error_type,
        details=details or {},
    )

    logger.info(
        f"[ERROR_CLASSIFY] type={error_type} category={classified.category.value} "
        f"severity={classified.severity.value} recovery={classified.recovery_action.value}"
    )
    return classified
