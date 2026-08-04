"""
Dependency injection registry.

Provides singleton factories for all domain services and repositories.
Repositories now use PostgreSQL. STT/TTS adapters are built dynamically
from the active bot's speech provider config.
"""

from typing import Optional, Dict, Any
from fastapi import Query
from app.shared.security.token_service import verify_token, AuthenticationError
from app.shared.events.event_bus import EventBus
from app.shared.config.runtime_limits import RuntimeLimits, get_limits
from app.shared.cancellation.cancellation_token import CancellationTokenSource
from app.shared.resources.session_resource_manager import SessionResourceManager
from app.shared.providers.provider_health_manager import ProviderHealthManager
from app.shared.capabilities.capability_registry import CapabilityRegistry
from app.shared.errors.error_classifier import classify_error, ErrorCategory, RecoveryAction
from app.shared.security.envelope_encryption import load_and_decrypt

from app.modules.session.domain.interfaces.session_repository_interface import SessionRepositoryInterface
from app.modules.session.infrastructure.persistence.postgres_session_repository import PostgresSessionRepository
from app.modules.message.domain.interfaces.message_repository_interface import MessageRepositoryInterface
from app.modules.message.infrastructure.persistence.postgres_message_repository import PostgresMessageRepository
from app.modules.conversation.domain.interfaces.response_repository_interface import ResponseRepositoryInterface
from app.modules.conversation.infrastructure.persistence.postgres_response_repository import PostgresResponseRepository
from app.modules.conversation.domain.interfaces.validation_provider_interface import ValidationProviderInterface
from app.modules.conversation.infrastructure.external.litellm_validation_adapter import LiteLLMValidationAdapter
from app.modules.interruption.domain.interfaces.interruption_repository_interface import InterruptionRepositoryInterface
from app.modules.interruption.infrastructure.persistence.postgres_interruption_repository import PostgresInterruptionRepository
from app.modules.interruption.infrastructure.external.interruption_classifier_adapter import InterruptionClassifierAdapter
from app.modules.voice.domain.interfaces.stt_provider_interface import STTProviderInterface
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface
from app.modules.voice.infrastructure.providers.provider_factory import SpeechProviderFactory
from app.modules.bot.infrastructure.persistence.postgres_bot_repository import PostgresBotRepository
from app.modules.provider.infrastructure.persistence.postgres_llm_provider_repository import PostgresLLMProviderRepository
from app.modules.provider.infrastructure.persistence.postgres_speech_provider_repository import PostgresSpeechProviderRepository
from app.modules.conversation.domain.policy.conversation_policy import ConversationPolicy
from app.modules.conversation.application.services.context_manager import ContextManager
from app.modules.conversation.application.services.task_router import TaskRouter
from app.modules.session.application.services.runtime_state_manager import RuntimeStateManager

# Singletons
_event_bus: Optional[EventBus] = None
_conversation_policy: Optional[ConversationPolicy] = None
_context_manager: Optional[ContextManager] = None
_task_router: Optional[TaskRouter] = None
_runtime_state_manager: Optional[RuntimeStateManager] = None
_provider_health: Optional[ProviderHealthManager] = None
_capability_registry: Optional[CapabilityRegistry] = None

# Repository singletons
_bot_repo: Optional[PostgresBotRepository] = None
_llm_provider_repo: Optional[PostgresLLMProviderRepository] = None
_speech_provider_repo: Optional[PostgresSpeechProviderRepository] = None


def get_event_bus() -> EventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def get_conversation_policy() -> ConversationPolicy:
    global _conversation_policy
    if _conversation_policy is None:
        _conversation_policy = ConversationPolicy(max_retries=3)
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
        _provider_health.register("stt")
        _provider_health.register("tts")
        _provider_health.register("llm")
    return _provider_health


def get_capability_registry() -> CapabilityRegistry:
    global _capability_registry
    if _capability_registry is None:
        _capability_registry = CapabilityRegistry()
        _capability_registry.register("streaming_stt", available=True, version="multi-provider")
        _capability_registry.register("streaming_tts", available=True, version="multi-provider")
        _capability_registry.register("rnnoise", available=False)
        _capability_registry.register("browser_dsp", available=True)
        _capability_registry.register("silero_vad", available=True, version="@ricky0123/vad-web")
        _capability_registry.register("barge_in", available=True)
        _capability_registry.register("audio_metrics", available=True)
        _capability_registry.register("audio_health_monitor", available=True)
        _capability_registry.register("runtime_diagnostics", available=True)
    return _capability_registry


def get_bot_repository() -> PostgresBotRepository:
    global _bot_repo
    if _bot_repo is None:
        _bot_repo = PostgresBotRepository()
    return _bot_repo


def get_llm_provider_repository() -> PostgresLLMProviderRepository:
    global _llm_provider_repo
    if _llm_provider_repo is None:
        _llm_provider_repo = PostgresLLMProviderRepository()
    return _llm_provider_repo


def get_speech_provider_repository() -> PostgresSpeechProviderRepository:
    global _speech_provider_repo
    if _speech_provider_repo is None:
        _speech_provider_repo = PostgresSpeechProviderRepository()
    return _speech_provider_repo


def get_session_repository() -> SessionRepositoryInterface:
    return PostgresSessionRepository()


def get_message_repository() -> MessageRepositoryInterface:
    return PostgresMessageRepository()


def get_response_repository() -> ResponseRepositoryInterface:
    return PostgresResponseRepository()


def get_interruption_repository() -> InterruptionRepositoryInterface:
    return PostgresInterruptionRepository()


async def build_speech_adapters_from_bot(bot: Dict[str, Any]):
    """
    Build STT and TTS adapters dynamically from the active bot's speech provider.
    Returns (stt_adapter, tts_adapter).
    """
    speech_provider_id = bot.get("speech_provider_id")
    if not speech_provider_id:
        raise ValueError(f"Bot '{bot['name']}' has no speech_provider_id configured")

    repo = get_speech_provider_repository()
    sp = await repo.get_by_id(speech_provider_id)
    if not sp:
        raise ValueError(f"Speech provider {speech_provider_id} not found")

    # Decrypt credentials
    creds = await load_and_decrypt(sp["credentials_enc"], sp["key_version"])

    config = {
        "provider_type": sp["provider_type"],
        "credentials": creds,
        "stt_model": sp["stt_model"],
        "stt_language": sp["stt_language"],
        "stt_extra": sp.get("stt_extra", {}),
        "tts_model": sp["tts_model"],
        "tts_voice_id": sp["tts_voice_id"],
        "tts_extra": sp.get("tts_extra", {}),
    }

    stt = SpeechProviderFactory.build_stt(config)
    tts = SpeechProviderFactory.build_tts(config)
    return stt, tts


async def build_llm_config_from_bot(bot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build LLM config from the active bot's LLM provider.
    Returns dict with api_key, base_url, model, system_prompt.
    """
    llm_provider_id = bot.get("llm_provider_id")
    if not llm_provider_id:
        raise ValueError(f"Bot '{bot['name']}' has no llm_provider_id configured")

    repo = get_llm_provider_repository()
    lp = await repo.get_by_id(llm_provider_id)
    if not lp:
        raise ValueError(f"LLM provider {llm_provider_id} not found")

    creds = await load_and_decrypt(lp["credentials_enc"], lp["key_version"])

    return {
        "api_key": creds.get("api_key", ""),
        "base_url": lp["base_url"],
        "model": bot.get("llm_model", ""),
        "system_prompt": bot.get("system_prompt", ""),
        "provider_type": lp["provider_type"],
    }


def get_validation_adapter() -> ValidationProviderInterface:
    return LiteLLMValidationAdapter()


def get_interruption_classifier_adapter() -> InterruptionClassifierAdapter:
    return InterruptionClassifierAdapter()


def get_current_user(token: Optional[str] = Query(None)) -> str:
    """Authentication dependency. Returns user_id or raises AuthenticationError."""
    return verify_token(token)
