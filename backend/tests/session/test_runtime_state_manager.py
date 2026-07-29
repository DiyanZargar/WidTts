import pytest
from app.modules.session.application.services.runtime_state_manager import (
    RuntimeStateManager, ConnectionState, PlaybackState, STTState, TTSState,
)


@pytest.fixture
def sm():
    return RuntimeStateManager()


def test_create_and_get_session(sm):
    sm.create_session("s1", "interview", user_id="u1")
    state = sm.get_session("s1")
    assert state is not None
    assert state.session_id == "s1"
    assert state.conversation_type == "interview"
    assert state.connection_state == ConnectionState.CONNECTED


def test_destroy_session(sm):
    sm.create_session("s1", "interview")
    sm.destroy_session("s1")
    assert sm.get_session("s1") is None


def test_list_active_sessions(sm):
    sm.create_session("s1", "interview")
    sm.create_session("s2", "interview")
    sm.destroy_session("s2")
    assert sm.list_active_sessions() == {"s1"}


def test_connection_state(sm):
    sm.create_session("s1", "interview")
    sm.set_connection_state("s1", ConnectionState.DISCONNECTED)
    assert sm.get_session("s1").connection_state == ConnectionState.DISCONNECTED


def test_turn_lifecycle(sm):
    sm.create_session("s1", "interview")
    sm.set_turn("s1", "turn-1", 0)
    assert sm.get_session("s1").current_turn_id == "turn-1"
    assert sm.get_session("s1").current_question_index == 0


def test_retry_increment(sm):
    sm.create_session("s1", "interview")
    assert sm.increment_retry("s1") == 1
    assert sm.increment_retry("s1") == 2
    sm.reset_retries("s1")
    assert sm.increment_retry("s1") == 1


def test_advance_question(sm):
    sm.create_session("s1", "interview")
    sm.increment_retry("s1")
    new_idx = sm.advance_question("s1")
    assert new_idx == 1
    assert sm.get_session("s1").retry_count == 0


def test_playback_state(sm):
    sm.create_session("s1", "interview")
    sm.set_playback_state("s1", PlaybackState.PLAYING, tts_text="Hello")
    state = sm.get_session("s1")
    assert state.playback_state == PlaybackState.PLAYING
    assert state.current_tts_text == "Hello"


def test_tts_chunk_recording(sm):
    sm.create_session("s1", "interview")
    sm.set_playback_state("s1", PlaybackState.PLAYING)
    sm.record_tts_chunk("s1", 1024)
    sm.record_tts_chunk("s1", 2048)
    state = sm.get_session("s1")
    assert state.tts_chunks_received == 2
    assert state.tts_bytes_received == 3072


def test_stt_tts_state(sm):
    sm.create_session("s1", "interview")
    sm.set_stt_state("s1", STTState.LISTENING)
    sm.set_tts_state("s1", TTSState.STREAMING)
    state = sm.get_session("s1")
    assert state.stt_state == STTState.LISTENING
    assert state.tts_state == TTSState.STREAMING


def test_epoch_advance(sm):
    sm.create_session("s1", "interview")
    assert sm.advance_epoch("s1") == 1
    assert sm.advance_epoch("s1") == 2
    assert sm.get_session("s1").listening_epoch == 2


def test_snapshot(sm):
    sm.create_session("s1", "interview", user_id="u1")
    snap = sm.snapshot("s1")
    assert snap["session_id"] == "s1"
    assert snap["conversation_type"] == "interview"
    assert snap["connection_state"] == "connected"


def test_snapshot_nonexistent(sm):
    assert sm.snapshot("nonexistent") == {}
