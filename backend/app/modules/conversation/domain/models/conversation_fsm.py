import logging
import time
from enum import Enum
from typing import Dict, Set

logger = logging.getLogger("conversation_fsm")


class ConversationState(str, Enum):
    """Business-level conversation states only.

    Transport-adjacent states (WAITING_FOR_TTS, TTS_PLAYING, LISTENING,
    TRANSCRIBING) have been removed — LiveKit owns transport lifecycle.
    """
    IDLE = "IDLE"
    ASKING = "ASKING"
    VALIDATING = "VALIDATING"
    RETRY = "RETRY"
    ADVANCE = "ADVANCE"
    NEXT_TURN = "NEXT_TURN"


class TurnStateTransitionError(Exception):
    """Raised when an illegal FSM state transition is attempted."""
    pass


# Allowed FSM State Transition Map
ALLOWED_TRANSITIONS: Dict[ConversationState, Set[ConversationState]] = {
    ConversationState.IDLE: {
        ConversationState.ASKING,
    },
    ConversationState.ASKING: {
        ConversationState.VALIDATING,
    },
    ConversationState.VALIDATING: {
        ConversationState.ADVANCE,
        ConversationState.RETRY,
    },
    ConversationState.RETRY: {
        ConversationState.ASKING,
    },
    ConversationState.ADVANCE: {
        ConversationState.NEXT_TURN,
    },
    ConversationState.NEXT_TURN: {
        ConversationState.ASKING,
    },
}


class ConversationFSM:

    def __init__(self, turn_id: str, question_id: str, initial_state: ConversationState = ConversationState.IDLE):
        self.turn_id = turn_id
        self.question_id = question_id
        self._current_state = initial_state
        self._history = [(initial_state, time.time(), "initialized")]

    @property
    def current_state(self) -> ConversationState:
        return self._current_state

    def transition_to(self, target_state: ConversationState, reason: str = "") -> ConversationState:
        if target_state not in ALLOWED_TRANSITIONS.get(self._current_state, set()):
            err_msg = (
                f"Illegal FSM state transition! Cannot transition from '{self._current_state.value}' "
                f"to '{target_state.value}' for turn_id='{self.turn_id}', question_id='{self.question_id}'. "
                f"Reason: {reason}"
            )
            logger.error(err_msg)
            raise TurnStateTransitionError(err_msg)

        old_state = self._current_state
        self._current_state = target_state
        now = time.time()
        self._history.append((target_state, now, reason))

        logger.info(
            f"[FSM TRANSITION] turn_id={self.turn_id} | question_id={self.question_id} | "
            f"{old_state.value} -> {target_state.value} | reason='{reason}'"
        )
        return self._current_state

    def get_history(self):
        return list(self._history)
