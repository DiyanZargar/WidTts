from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, field
import time
import logging

logger = logging.getLogger("runtime_state")


@dataclass
class SessionRuntimeState:
    """Runtime state for a conversation session.

    Transport-level state (ConnectionState, PlaybackState, STTState, TTSState,
    websocket_id, playback_state, current_tts_text, tts_chunks_received,
    tts_bytes_received, listening_epoch) removed — LiveKit owns transport
    lifecycle. Only business-level state remains.
    """
    session_id: str
    conversation_type: str = ""
    user_id: str = ""
    created_at: float = field(default_factory=time.time)

    # Turn
    current_turn_id: Optional[str] = None
    current_question_index: int = 0
    retry_count: int = 0

    # Flags
    is_recovery: bool = False
    is_destroyed: bool = False


class RuntimeStateManager:
    """
    Single source of truth for all runtime state.

    Responsibilities:
    - Track session, turn lifecycle
    - Provide atomic state transitions with validation
    - Expose read-only snapshots to other components
    - Clean up state on session end

    Transport state previously here (connection, playback, STT, TTS,
    audio pipeline) is now owned by LiveKit.
    """

    def __init__(self):
        self._sessions: Dict[str, SessionRuntimeState] = {}

    # --- Lifecycle ---

    def create_session(
        self,
        session_id: str,
        conversation_type: str,
        user_id: str = "",
        is_recovery: bool = False,
    ) -> SessionRuntimeState:
        state = SessionRuntimeState(
            session_id=session_id,
            conversation_type=conversation_type,
            user_id=user_id,
            is_recovery=is_recovery,
        )
        self._sessions[session_id] = state
        logger.info(f"[RUNTIME_STATE] Created session {session_id} type={conversation_type}")
        return state

    def get_session(self, session_id: str) -> Optional[SessionRuntimeState]:
        return self._sessions.get(session_id)

    def destroy_session(self, session_id: str) -> None:
        state = self._sessions.pop(session_id, None)
        if state:
            state.is_destroyed = True
            logger.info(f"[RUNTIME_STATE] Destroyed session {session_id}")

    def list_active_sessions(self) -> Set[str]:
        return {sid for sid, s in self._sessions.items() if not s.is_destroyed}

    # --- Turn ---

    def set_turn(self, session_id: str, turn_id: str, question_index: int) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.current_turn_id = turn_id
            s.current_question_index = question_index

    def increment_retry(self, session_id: str) -> int:
        s = self._sessions.get(session_id)
        if s:
            s.retry_count += 1
            return s.retry_count
        return 0

    def reset_retries(self, session_id: str) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.retry_count = 0

    def advance_question(self, session_id: str) -> int:
        s = self._sessions.get(session_id)
        if s:
            s.current_question_index += 1
            s.retry_count = 0
            return s.current_question_index
        return 0

    # --- Snapshots ---

    def snapshot(self, session_id: str) -> Dict[str, Any]:
        """Return a read-only snapshot of current state."""
        s = self._sessions.get(session_id)
        if not s:
            return {}
        return {
            "session_id": s.session_id,
            "conversation_type": s.conversation_type,
            "user_id": s.user_id,
            "current_turn_id": s.current_turn_id,
            "current_question_index": s.current_question_index,
            "retry_count": s.retry_count,
            "is_recovery": s.is_recovery,
        }
