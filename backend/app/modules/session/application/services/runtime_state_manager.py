from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import time
import logging

logger = logging.getLogger("runtime_state")


class ConnectionState(str, Enum):
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"


class PlaybackState(str, Enum):
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    INTERRUPTED = "interrupted"


class STTState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    LISTENING = "listening"
    PROCESSING = "processing"


class TTSState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    SYNTHESIZING = "synthesizing"
    STREAMING = "streaming"


@dataclass
class SessionRuntimeState:
    session_id: str
    conversation_type: str = ""
    user_id: str = ""
    created_at: float = field(default_factory=time.time)

    # Connection
    connection_state: ConnectionState = ConnectionState.CONNECTING
    websocket_id: Optional[str] = None

    # Turn
    current_turn_id: Optional[str] = None
    current_question_index: int = 0
    retry_count: int = 0

    # Playback
    playback_state: PlaybackState = PlaybackState.IDLE
    current_tts_text: str = ""
    tts_chunks_received: int = 0
    tts_bytes_received: int = 0

    # Audio pipeline
    stt_state: STTState = STTState.DISCONNECTED
    tts_state: TTSState = TTSState.DISCONNECTED
    listening_epoch: int = 0

    # Flags
    is_recovery: bool = False
    is_destroyed: bool = False


class RuntimeStateManager:
    """
    Single source of truth for all runtime state.

    Responsibilities:
    - Track session, turn, playback, STT, TTS, and connection state
    - Provide atomic state transitions with validation
    - Expose read-only snapshots to other components
    - Clean up state on session end

    Previously this state was scattered across:
    - ConnectionManager.active (connection)
    - TurnContext (turn + FSM)
    - audioVolumeTracker (frontend playback)
    - Inline variables in conversation_handler (index, retries, current_tts_text)
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
            connection_state=ConnectionState.CONNECTED,
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

    # --- Connection ---

    def set_connection_state(self, session_id: str, state: ConnectionState) -> None:
        s = self._sessions.get(session_id)
        if s:
            old = s.connection_state
            s.connection_state = state
            logger.debug(f"[RUNTIME_STATE] Connection {session_id}: {old.value} -> {state.value}")

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

    # --- Playback ---

    def set_playback_state(self, session_id: str, state: PlaybackState, tts_text: str = "") -> None:
        s = self._sessions.get(session_id)
        if s:
            old = s.playback_state
            s.playback_state = state
            if tts_text:
                s.current_tts_text = tts_text
            if state == PlaybackState.PLAYING:
                s.tts_chunks_received = 0
                s.tts_bytes_received = 0
            logger.debug(f"[RUNTIME_STATE] Playback {session_id}: {old.value} -> {state.value}")

    def record_tts_chunk(self, session_id: str, chunk_bytes: int) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.tts_chunks_received += 1
            s.tts_bytes_received += chunk_bytes

    # --- Audio pipeline ---

    def set_stt_state(self, session_id: str, state: STTState) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.stt_state = state

    def set_tts_state(self, session_id: str, state: TTSState) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.tts_state = state

    def advance_epoch(self, session_id: str) -> int:
        s = self._sessions.get(session_id)
        if s:
            s.listening_epoch += 1
            return s.listening_epoch
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
            "connection_state": s.connection_state.value,
            "current_turn_id": s.current_turn_id,
            "current_question_index": s.current_question_index,
            "retry_count": s.retry_count,
            "playback_state": s.playback_state.value,
            "stt_state": s.stt_state.value,
            "tts_state": s.tts_state.value,
            "listening_epoch": s.listening_epoch,
            "tts_chunks_received": s.tts_chunks_received,
            "tts_bytes_received": s.tts_bytes_received,
            "is_recovery": s.is_recovery,
        }
