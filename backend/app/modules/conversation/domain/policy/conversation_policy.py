from typing import Dict, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger("conversation_policy")


class PolicyAction(str, Enum):
    STOP = "stop"                          # User wants assistant to stop talking
    REPEAT = "repeat"                      # User wants question repeated
    CONTINUE = "continue"                  # Resume after stop
    FORGET = "forget"                      # Discard last answer
    CORRECTION = "correction"              # User is correcting themselves
    ANSWER = "answer"                      # Normal answer to question
    END_CONVERSATION = "end_conversation"  # Reset and start over
    NONE = "none"                          # Unclassified / no action


class ConversationPolicy:
    """
    Centralized conversational behavior rules.

    Responsibilities:
    - Map interruption types to policy actions
    - Define retry limits and escalation rules
    - Handle conversation commands (repeat, stop, continue, forget)
    - Keep all behavioral rules in one testable place

    The Conversation Engine asks: "Given this classification, what should we do?"
    """

    # Deterministic system commands — exact string matches for instant response
    _STOP_COMMANDS = {"stop", "stop talking", "be quiet", "shut up", "pause", "quiet"}
    _END_COMMANDS = {"end", "end conversation", "start over", "reset", "quit", "i'm done", "goodbye"}
    _REPEAT_COMMANDS = {"repeat", "say that again", "what did you say", "pardon"}
    _CONTINUE_COMMANDS = {"continue", "go on", "proceed", "keep going"}
    _FORGET_COMMANDS = {"forget that", "never mind", "disregard", "ignore that"}

    def __init__(self, max_retries: Optional[int] = None):
        self.max_retries = max_retries

    def resolve_action(
        self,
        classification_type: str,
        transcript: str,
        current_retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Convert an interruption classification into a concrete policy action.

        Returns dict with:
        - action: PolicyAction
        - should_advance: bool
        - reason: str (human-readable explanation)
        - max_retries_exceeded: bool
        - next_state: str (suggested FSM state)
        """
        t = transcript.strip().lower()

        # --- Deterministic routing (bypass classification for known commands) ---
        if t in self._STOP_COMMANDS:
            return self._action(PolicyAction.STOP, "User requested stop")

        if t in self._END_COMMANDS:
            return self._action(PolicyAction.END_CONVERSATION, "User requested conversation reset")

        if t in self._REPEAT_COMMANDS:
            return self._action(PolicyAction.REPEAT, "User requested repeat")

        if t in self._CONTINUE_COMMANDS:
            return self._action(PolicyAction.CONTINUE, "User requested continue")

        if t in self._FORGET_COMMANDS:
            return self._action(PolicyAction.FORGET, "User requested forget")

        # --- Classification-based routing ---
        if classification_type == "STOP":
            return self._action(PolicyAction.STOP, "Classification: STOP")

        if classification_type == "END_CONVERSATION":
            return self._action(PolicyAction.END_CONVERSATION, "Classification: END_CONVERSATION")

        if classification_type == "REPEAT":
            return self._action(PolicyAction.REPEAT, "Classification: REPEAT")

        if classification_type == "CORRECTION":
            return self._action(PolicyAction.CORRECTION, "Classification: CORRECTION")

        if classification_type == "ANSWER":
            return self._action(PolicyAction.ANSWER, "Classification: ANSWER")

        # --- Fallback ---
        return self._action(PolicyAction.NONE, "Unrecognized classification")

    def evaluate_retry(
        self,
        current_retry_count: int,
        validation_passed: bool,
    ) -> Dict[str, Any]:
        """
        Decide what happens after validation: advance, retry, or max-retries escalation.
        """
        if validation_passed:
            return {
                "action": PolicyAction.ANSWER,
                "should_advance": True,
                "reason": "Validation passed",
                "max_retries_exceeded": False,
                "next_state": "ADVANCE",
                "retry_increment": 0,
            }

        if self.max_retries is not None and current_retry_count >= self.max_retries:
            return {
                "action": PolicyAction.ANSWER,
                "should_advance": True,
                "reason": f"Max retries ({self.max_retries}) exceeded — auto-advancing",
                "max_retries_exceeded": True,
                "next_state": "ADVANCE",
                "retry_increment": 0,
            }

        return {
            "action": PolicyAction.ANSWER,
            "should_advance": False,
            "reason": "Validation failed — retrying",
            "max_retries_exceeded": False,
            "next_state": "RETRY",
            "retry_increment": 1,
        }

    def _action(self, action: PolicyAction, reason: str) -> Dict[str, Any]:
        return {
            "action": action,
            "should_advance": action == PolicyAction.ANSWER,
            "reason": reason,
            "max_retries_exceeded": False,
            "next_state": action.value.upper(),
            "retry_increment": 0,
        }
