import pytest
import asyncio
from app.modules.conversation.domain.models.conversation_fsm import (
    ConversationFSM,
    ConversationState,
    TurnStateTransitionError,
)
from app.modules.conversation.domain.models.turn_context import TurnContext


def test_fsm_valid_transitions():
    fsm = ConversationFSM(turn_id="t1", question_id="q1")
    assert fsm.current_state == ConversationState.IDLE

    fsm.transition_to(ConversationState.ASKING)
    assert fsm.current_state == ConversationState.ASKING

    fsm.transition_to(ConversationState.WAITING_FOR_TTS)
    assert fsm.current_state == ConversationState.WAITING_FOR_TTS

    fsm.transition_to(ConversationState.TTS_PLAYING)
    assert fsm.current_state == ConversationState.TTS_PLAYING

    fsm.transition_to(ConversationState.LISTENING)
    assert fsm.current_state == ConversationState.LISTENING

    fsm.transition_to(ConversationState.TRANSCRIBING)
    assert fsm.current_state == ConversationState.TRANSCRIBING

    fsm.transition_to(ConversationState.VALIDATING)
    assert fsm.current_state == ConversationState.VALIDATING

    fsm.transition_to(ConversationState.ADVANCE)
    assert fsm.current_state == ConversationState.ADVANCE


def test_fsm_illegal_transition_raises_error():
    fsm = ConversationFSM(turn_id="t1", question_id="q1")
    assert fsm.current_state == ConversationState.IDLE

    # Direct jump from IDLE to VALIDATING is illegal
    with pytest.raises(TurnStateTransitionError):
        fsm.transition_to(ConversationState.VALIDATING)


@pytest.mark.asyncio
async def test_turn_context_task_cancellation_on_destroy():
    turn = TurnContext(
        session_id="s1",
        conversation_id="c1",
        question_id="q1",
        sequence_number=0,
        question_text="How are you?",
        expected_context="status",
    )

    async def dummy_long_task():
        await asyncio.sleep(10)

    task = asyncio.create_task(dummy_long_task())
    turn.register_task(task)

    assert task in turn.active_tasks
    assert not task.cancelled()

    turn.destroy()
    await asyncio.sleep(0)

    assert turn.is_destroyed
    assert len(turn.active_tasks) == 0
    assert task.cancelled() or task.cancelling() > 0


def test_turn_context_event_validation():
    turn = TurnContext(
        session_id="s1",
        conversation_id="c1",
        question_id="q1",
        sequence_number=0,
        question_text="How are you?",
        expected_context="status",
    )

    # Valid event matching turn attributes
    assert turn.is_event_valid(turn_id=turn.turn_id, question_id="q1", session_id="s1") is True

    # Mismatched turn_id rejected
    assert turn.is_event_valid(turn_id="other_turn", question_id="q1", session_id="s1") is False

    # Mismatched question_id rejected
    assert turn.is_event_valid(turn_id=turn.turn_id, question_id="q2", session_id="s1") is False

    # Mismatched session_id rejected
    assert turn.is_event_valid(turn_id=turn.turn_id, question_id="q1", session_id="s2") is False

    turn.destroy()
    # Destroyed turn rejects all events
    assert turn.is_event_valid(turn_id=turn.turn_id, question_id="q1", session_id="s1") is False


def test_turn_context_correction():
    turn = TurnContext(
        session_id="s1",
        conversation_id="c1",
        question_id="q1",
        sequence_number=0,
        question_text="What's your name?",
        expected_context="name",
    )

    # Set initial answer
    turn.set_final_transcript("John")
    assert turn.final_transcript == "John"
    assert len(turn.correction_stack) == 0

    # Apply correction
    turn.apply_correction("Jonathan")
    assert turn.final_transcript == "Jonathan"
    assert len(turn.correction_stack) == 1
    assert turn.correction_stack[0]["text"] == "John"
    assert turn.final_transcript_consumed is False  # Reset for re-validation

    # Apply another correction
    turn.apply_correction("Jon")
    assert turn.final_transcript == "Jon"
    assert len(turn.correction_stack) == 2
    assert turn.correction_stack[0]["text"] == "John"
    assert turn.correction_stack[1]["text"] == "Jonathan"

    turn.destroy()
    assert len(turn.correction_stack) == 0  # Cleared on destroy


@pytest.mark.asyncio
async def test_turn_context_cancel_active_validation():
    turn = TurnContext(
        session_id="s1",
        conversation_id="c1",
        question_id="q1",
        sequence_number=0,
        question_text="What's your name?",
        expected_context="name",
    )

    # No active task
    assert turn.cancel_active_validation() is False

    # Create a mock task
    async def dummy_task():
        await asyncio.sleep(10)

    task = asyncio.create_task(dummy_task())
    turn.active_validation_task = task
    assert turn.cancel_active_validation() is True
    assert task.cancelled() or task.cancelling() > 0
    assert turn.active_validation_task is None

    turn.destroy()
