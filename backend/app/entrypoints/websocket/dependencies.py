from typing import Optional
from fastapi import Query
from app.shared.security.token_service import verify_token, AuthenticationError
from app.shared.events.event_bus import EventBus
from app.shared.config.runtime_limits import RuntimeLimits, get_limits
from app.shared.cancellation.cancellation_token import CancellationTokenSource
from app.shared.resources.session_resource_manager import SessionResourceManager
from app.shared.providers.provider_health_manager import ProviderHealthManager
from app.shared.capabilities.capability_registry import CapabilityRegistry
from app.shared.errors.error_classifier import classify_error, ErrorCategory, RecoveryAction

from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface
from app.modules.session.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface
from app.modules.message.infrastructure.persistence.sqlite_message_repository import SqliteMessageRepository
from app.modules.conversation.domain.interfaces.conversation_repository_interface import ConversationRepositoryInterface
from app.modules.conversation.infrastructure.external.json_conversation_repository import JsonConversationRepository
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface
from app.modules.conversation.infrastructure.persistence.sqlite_response_repository import SqliteResponseRepository
from app.modules.conversation.domain.interfaces.validation_provider_interface import ValidationProviderInterface
from app.modules.conversation.infrastructure.external.litellm_validation_adapter import LiteLLMValidationAdapter
from app.modules.interruption.domain.interfaces.interruption_repository_interface import InterruptionRepositoryInterface
from app.modules.interruption.infrastructure.persistence.sqlite_interruption_repository import SqliteInterruptionRepository
from app.modules.interruption.infrastructure.external.interruption_classifier_adapter import InterruptionClassifierAdapter
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface
from app.modules.voice.infrastructure.external.deepgram_stt_adapter import DeepgramSTTAdapter
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface
from app.modules.voice.infrastructure.external.deepgram_tts_adapter import DeepgramTTSAdapter
from app.modules.conversation.domain.policy.conversation_policy import ConversationPolicy
from app.modules.conversation.application.services.context_manager import ContextManager
from app.modules.conversation.application.services.task_router import TaskRouter
from app.modules.session.application.services.runtime_state_manager import RuntimeStateManager

# Singletons
_json_conversation_repo: Optional[JsonConversationRepository] = None
_event_bus: Optional[EventBus] = None
_conversation_policy: Optional[ConversationPolicy] = None
_context_manager: Optional[ContextManager] = None
_task_router: Optional[TaskRouter] = None
_runtime_state_manager: Optional[RuntimeStateManager] = None
_provider_health: Optional[ProviderHealthManager] = None
_capability_registry: Optional[CapabilityRegistry] = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def get_conversation_policy() -> ConversationPolicy:
    global _conversation_policy
    if _conversation_policy is None:
        from app.shared.config.settings import settings
        _conversation_policy = ConversationPolicy(max_retries=settings.max_retries_per_item)
    return _conversation_policy


def get_context_manager() -> ContextManager:
    global _context_manager
    if _context_manager is None:
        _context_manager = ContextManager(max_tokens=get_limits().max_context_tokens)
    return _context_manager


def get_task_router() -> TaskRouter:
    global _task_router
    if _task_router is None:
        _task_router = TaskRouter()
    return _task_router


def get_runtime_state_manager() -> RuntimeStateManager:
    global _runtime_state_manager
    if _runtime_state_manager is None:
        _runtime_state_manager = RuntimeStateManager()
    return _runtime_state_manager


def get_provider_health() -> ProviderHealthManager:
    global _provider_health
    if _provider_health is None:
        _provider_health = ProviderHealthManager()
        _provider_health.register("deepgram_stt")
        _provider_health.register("deepgram_tts")
        _provider_health.register("litellm")
    return _provider_health


def get_capability_registry() -> CapabilityRegistry:
    global _capability_registry
    if _capability_registry is None:
        _capability_registry = CapabilityRegistry()
        _capability_registry.register("streaming_stt", available=True, version="deepgram-sdk-7.6.0")
        _capability_registry.register("streaming_tts", available=True, version="deepgram-sdk-7.6.0")
        _capability_registry.register("rnnoise", available=False)
        _capability_registry.register("browser_dsp", available=True)
        _capability_registry.register("silero_vad", available=True, version="@ricky0123/vad-web")
        _capability_registry.register("barge_in", available=True)
        _capability_registry.register("audio_metrics", available=True)
        _capability_registry.register("audio_health_monitor", available=True)
        _capability_registry.register("runtime_diagnostics", available=True)
    return _capability_registry


def get_conversation_repository() -> ConversationRepositoryInterface:
    global _json_conversation_repo
    if _json_conversation_repo is None:
        _json_conversation_repo = JsonConversationRepository()
    return _json_conversation_repo


def get_session_repository() -> SessionRepositoryInterface:
    return SqliteSessionRepository()


def get_message_repository() -> MessageRepositoryInterface:
    return SqliteMessageRepository()


def get_response_repository() -> ResponseRepositoryInterface:
    return SqliteResponseRepository()


def get_interruption_repository() -> InterruptionRepositoryInterface:
    return SqliteInterruptionRepository()


def get_stt_adapter() -> STTProviderInterface:
    return DeepgramSTTAdapter()


def get_tts_adapter() -> TTSProviderInterface:
    return DeepgramTTSAdapter()


def get_validation_adapter() -> ValidationProviderInterface:
    return LiteLLMValidationAdapter()


def get_interruption_classifier_adapter() -> InterruptionClassifierAdapter:
    return InterruptionClassifierAdapter()


def get_current_user(token: Optional[str] = Query(None)) -> str:
    """Authentication dependency. Returns user_id or raises AuthenticationError."""
    return verify_token(token)
