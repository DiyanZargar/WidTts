import uuid
import time
import asyncio
import logging
from enum import Enum
from typing import Optional, List, Dict, Any, Set
from app.modules.conversation.domain.models.conversation_fsm import ConversationFSM, ConversationState

logger = logging.getLogger("turn_context")


class TranscriptLifecycle(str, Enum):
    """Deterministic lifecycle stages for every transcript.

    Transport-level stages (QUEUED, DISCARDED) removed — LiveKit owns
    the STT pipeline and queue management.
    """
    CREATED = "CREATED"            # Transcript object instantiated with unique ID
    ASSIGNED = "ASSIGNED"          # Transcript bound to a specific TurnContext
    VALIDATED = "VALIDATED"        # Transcript passed through LLM validation
    CONSUMED = "CONSUMED"          # Transcript applied to conversation state
    DESTROYED = "DESTROYED"        # TurnContext destroyed — all transcripts cleaned


class TurnContext:
    """Transactional context encapsulating state and resources for a single turn."""

    def __init__(
        self,
        session_id: str,
        conversation_id: str,
        question_id: str,
        sequence_number: int,
        question_text: str,
        expected_context: str,
        retry_counter: int = 0,
    ):
        self.turn_id: str = str(uuid.uuid4())
        self.session_id: str = session_id
        self.conversation_id: str = conversation_id
        self.question_id: str = question_id
        self.sequence_number: int = sequence_number
        self.question_text: str = question_text
        self.expected_context: str = expected_context
        self.retry_counter: int = retry_counter

        self.fsm: ConversationFSM = ConversationFSM(
            turn_id=self.turn_id,
            question_id=self.question_id,
            initial_state=ConversationState.IDLE,
        )

        # ── Transcript ownership & lifecycle ──
        self.partial_transcripts: List[Dict[str, Any]] = []
        self.final_transcript: Optional[str] = None
        self.transcript_id: Optional[str] = None
        self.transcript_created_at: Optional[float] = None
        self.transcript_lifecycle: TranscriptLifecycle = TranscriptLifecycle.CREATED
        self.final_transcript_consumed: bool = False

        # ── Correction tracking ──
        self.correction_stack: List[Dict[str, Any]] = []
        self.active_validation_task: Optional[asyncio.Task] = None
        self.active_llm_task: Optional[asyncio.Task] = None
        # ── Turn timing ──
        self.created_at: float = time.time()
        self.last_transcript_at: Optional[float] = None    # Timestamp of last accepted transcript

        # ── Async task management ──
        self.active_tasks: Set[asyncio.Task] = set()
        self.is_destroyed: bool = False

        # ── Validation result ──
        self.validation_result: Optional[Dict[str, Any]] = None

    # ──────────────────────────────────────────────
    #  Ownership verification
    # ──────────────────────────────────────────────

    def is_event_valid(
        self,
        turn_id: Optional[str],
        question_id: Optional[str],
        session_id: Optional[str],
    ) -> bool:
        """Verify strict ownership before processing any event."""
        if self.is_destroyed:
            logger.warning(
                f"[TURN REJECT] Event received on destroyed TurnContext "
                f"turn_id={self.turn_id} session_id={self.session_id} "
                f"question_id={self.question_id}"
            )
            return False

        if session_id and session_id != self.session_id:
            logger.warning(
                f"[TURN REJECT] Session mismatch: target={session_id} != bound={self.session_id} "
                f"turn_id={self.turn_id}"
            )
            return False

        if question_id and question_id != self.question_id:
            logger.warning(
                f"[TURN REJECT] Question mismatch: target={question_id} != bound={self.question_id} "
                f"turn_id={self.turn_id}"
            )
            return False

        if turn_id and turn_id != self.turn_id:
            logger.warning(
                f"[TURN REJECT] Turn mismatch: target={turn_id} != bound={self.turn_id} "
                f"question_id={self.question_id}"
            )
            return False

        return True

    # ──────────────────────────────────────────────
    #  Transcript acceptance
    # ──────────────────────────────────────────────

    def can_accept_transcript(self) -> bool:
        """Check whether this turn can accept an incoming transcript.

        Rejects if:
        - Turn is destroyed
        - A final transcript has already been consumed
        """
        if self.is_destroyed:
            logger.warning(
                f"[TRANSCRIPT REJECT] Turn destroyed — "
                f"turn_id={self.turn_id} question_id={self.question_id}"
            )
            return False

        if self.final_transcript_consumed:
            logger.warning(
                f"[TRANSCRIPT REJECT] Transcript already consumed — "
                f"turn_id={self.turn_id} transcript_id={self.transcript_id}"
            )
            return False

        return True

    # ──────────────────────────────────────────────
    #  Transcript lifecycle
    # ──────────────────────────────────────────────

    def add_partial_transcript(self, text: str) -> None:
        """Record an interim (non-final) transcript fragment.

        B10: Consecutive duplicates are silently skipped.
        B9: The list is capped at the 50 most recent entries.
        """
        if not self.is_destroyed and text:
            # B10: Skip consecutive duplicate partials
            if self.partial_transcripts and self.partial_transcripts[-1]["text"] == text:
                return

            entry = {
                "text": text,
                "received_at": time.time(),
            }
            self.partial_transcripts.append(entry)

            # B9: Cap to last 50 entries
            if len(self.partial_transcripts) > 50:
                self.partial_transcripts = self.partial_transcripts[-50:]

            logger.debug(
                f"[TRANSCRIPT PARTIAL] turn_id={self.turn_id} "
                f"question_id={self.question_id} text='{text}'"
            )

    def set_final_transcript(self, text: str) -> str:
        """Assign final transcript with unique transcript_id and reset consumption state.

        Returns the new transcript_id, or empty string if rejected.
        """
        if self.is_destroyed:
            logger.warning(
                f"[TRANSCRIPT REJECT] Cannot set final on destroyed turn — "
                f"turn_id={self.turn_id}"
            )
            return ""

        if not text:
            return ""

        # Prevent double-assignment within the same listening cycle
        if self.final_transcript is not None and not self.final_transcript_consumed:
            logger.info(
                f"[TRANSCRIPT UPDATE] Replacing final transcript — "
                f"turn_id={self.turn_id} old='{self.final_transcript}' new='{text}'"
            )

        self.final_transcript = text
        self.transcript_id = str(uuid.uuid4())
        self.transcript_created_at = time.time()
        self.final_transcript_consumed = False
        self.transcript_lifecycle = TranscriptLifecycle.ASSIGNED
        self.last_transcript_at = self.transcript_created_at

        logger.info(
            f"[TRANSCRIPT CREATED] turn_id={self.turn_id} "
            f"question_id={self.question_id} "
            f"transcript_id={self.transcript_id} "
            f"text='{self.final_transcript[:80]}' "
            f"created_at={self.transcript_created_at:.3f}"
        )
        return self.transcript_id

    def mark_transcript_consumed(self) -> None:
        """Mark transcript as consumed — guarantees single-consumption lifecycle."""
        if self.is_destroyed:
            return

        if self.final_transcript_consumed:
            logger.warning(
                f"[TRANSCRIPT DOUBLE-CONSUME] Attempted to consume already-consumed transcript — "
                f"turn_id={self.turn_id} transcript_id={self.transcript_id}"
            )
            return

        if not self.transcript_id:
            logger.warning(
                f"[TRANSCRIPT CONSUME] No transcript to consume — "
                f"turn_id={self.turn_id}"
            )
            return

        self.final_transcript_consumed = True
        self.transcript_lifecycle = TranscriptLifecycle.CONSUMED
        logger.info(
            f"[TRANSCRIPT CONSUMED] turn_id={self.turn_id} "
            f"question_id={self.question_id} "
            f"transcript_id={self.transcript_id} "
            f"text='{self.final_transcript[:80]}'"
        )

    def apply_correction(self, new_transcript: str) -> None:
        """Replace the current answer with a correction.

        Pushes the old answer onto the correction stack (for audit trail).
        The turn now owns only the new answer. Any in-flight validation
        task is cancelled — only the corrected answer will be validated.
        """
        if self.is_destroyed:
            logger.warning(
                f"[CORRECTION REJECT] Cannot apply correction on destroyed turn — "
                f"turn_id={self.turn_id}"
            )
            return

        # Archive the current answer
        if self.final_transcript:
            self.correction_stack.append({
                "transcript_id": self.transcript_id,
                "text": self.final_transcript,
                "replaced_at": time.time(),
            })
            logger.info(
                f"[CORRECTION ARCHIVE] turn_id={self.turn_id} "
                f"archived_answer='{self.final_transcript[:80]}' "
                f"correction_depth={len(self.correction_stack)}"
            )

        # Cancel any in-flight validation
        self.cancel_active_validation()
        self.cancel_active_llm()

        # Replace with the corrected answer
        self.final_transcript = new_transcript
        self.transcript_id = str(uuid.uuid4())
        self.transcript_created_at = time.time()
        self.final_transcript_consumed = False
        self.transcript_lifecycle = TranscriptLifecycle.ASSIGNED
        self.last_transcript_at = self.transcript_created_at

        logger.info(
            f"[CORRECTION APPLIED] turn_id={self.turn_id} "
            f"question_id={self.question_id} "
            f"new_transcript_id={self.transcript_id} "
            f"new_text='{new_transcript[:80]}'"
        )

    def cancel_active_validation(self) -> bool:
        """Cancel the currently running validation task, if any.

        Returns True if a task was cancelled, False if none was active.
        """
        if self.active_validation_task and not self.active_validation_task.done():
            self.active_validation_task.cancel()
            logger.info(
                f"[VALIDATION CANCELLED] turn_id={self.turn_id} "
                f"question_id={self.question_id}"
            )
            self.active_validation_task = None
            return True
        self.active_validation_task = None
        return False

    def cancel_active_llm(self) -> bool:
        """Cancel the currently running LLM streaming task, if any.

        Returns True if a task was cancelled, False if none was active.
        """
        if self.active_llm_task and not self.active_llm_task.done():
            self.active_llm_task.cancel()
            logger.info(
                f"[LLM CANCELLED] turn_id={self.turn_id} "
                f"question_id={self.question_id}"
            )
            self.active_llm_task = None
            return True
        self.active_llm_task = None
        return False

    def mark_transcript_discarded(self, reason: str = "") -> None:
        """Explicitly discard a transcript with a logged reason."""
        if self.is_destroyed:
            return

        logger.info(
            f"[TRANSCRIPT DISCARDED] turn_id={self.turn_id} "
            f"question_id={self.question_id} "
            f"transcript_id={self.transcript_id} "
            f"reason='{reason}'"
        )

    # ──────────────────────────────────────────────
    #  Async task management
    # ──────────────────────────────────────────────

    def register_task(self, task: asyncio.Task) -> None:
        """Track active async task owned by this turn."""
        if self.is_destroyed:
            logger.warning(
                f"[TASK REJECT] Attempted to register task on destroyed turn — "
                f"turn_id={self.turn_id}"
            )
            task.cancel()
            return

        self.active_tasks.add(task)
        task.add_done_callback(lambda t: self.active_tasks.discard(t))
        logger.debug(
            f"[TASK REGISTER] turn_id={self.turn_id} task_count={len(self.active_tasks)}"
        )

    def cancel_all_tasks(self) -> int:
        """Cancel all pending async tasks owned by this turn. Returns count cancelled."""
        cancelled = 0
        for task in list(self.active_tasks):
            if not task.done():
                task.cancel()
                cancelled += 1
        self.active_tasks.clear()
        if cancelled:
            logger.info(
                f"[TASK CANCEL] turn_id={self.turn_id} cancelled={cancelled}"
            )
        return cancelled

    # ──────────────────────────────────────────────
    #  Destruction
    # ──────────────────────────────────────────────

    def destroy(self) -> None:
        """Destroy the turn context, cancel pending async tasks, and clear buffers."""
        if self.is_destroyed:
            return

        self.is_destroyed = True
        logger.info(
            f"[TURN DESTROY] Destroying TurnContext "
            f"turn_id={self.turn_id} session_id={self.session_id} "
            f"question_id={self.question_id} "
            f"lifecycle={self.transcript_lifecycle.value} "
            f"tasks_remaining={len(self.active_tasks)} "
            f"corrections={len(self.correction_stack)}"
        )

        # Cancel active validation task
        self.cancel_active_validation()

        # Cancel all active tasks owned by this turn
        self.cancel_all_tasks()

        # Clear temporary buffers
        self.partial_transcripts.clear()
        self.final_transcript = None
        self.transcript_id = None
        self.transcript_created_at = None
        self.final_transcript_consumed = False
        self.transcript_lifecycle = TranscriptLifecycle.DESTROYED
        self.validation_result = None
        self.last_transcript_at = None
        self.correction_stack.clear()
        self.active_validation_task = None
