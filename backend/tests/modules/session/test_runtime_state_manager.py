import pytest
from app.modules.session.application.services.runtime_state_manager import (
    RuntimeStateManager, ConnectionState, PlaybackState, STTState, TTSState
)


@pytest.fixture
def rsm():
    return RuntimeStateManager()


def test_create_and_get_session(rsm):
    s = rsm.create_session("s1", "interview", user_id="u1")
    assert s.session_id == "s1"
    assert s.conversation_type == "interview"
    assert rsm.get_session("s1") is s


def test_connection_state(rsm):
    rsm.create_session("s1", "interview")
    rsm.set_connection_state("s1", ConnectionState.DISCONNECTED)
    assert rsm.get_session("s1").connection_state == ConnectionState.DISCONNECTED


def test_turn_and_retry(rsm):
    rsm.create_session("s1", "interview")
    rsm.set_turn("s1", "turn-1", 0)
    rsm.increment_retry("s1")
    rsm.increment_retry("s1")
    s = rsm.get_session("s1")
    assert s.current_turn_id == "turn-1"
    assert s.retry_count == 2

    rsm.reset_retries("s1")
    assert s.retry_count == 0


def test_advance_question(rsm):
    rsm.create_session("s1", "interview")
    rsm.set_turn("s1", "turn-1", 0)
    idx = rsm.advance_question("s1")
    assert idx == 1
    assert rsm.get_session("s1").current_question_index == 1


def test_playback_state(rsm):
    rsm.create_session("s1", "interview")
    rsm.set_playback_state("s1", PlaybackState.PLAYING, tts_text="Hello")
    s = rsm.get_session("s1")
    assert s.playback_state == PlaybackState.PLAYING
    assert s.current_tts_text == "Hello"


def test_record_tts_chunk(rsm):
    rsm.create_session("s1", "interview")
    rsm.record_tts_chunk("s1", 1024)
    rsm.record_tts_chunk("s1", 512)
    s = rsm.get_session("s1")
    assert s.tts_chunks_received == 2
    assert s.tts_bytes_received == 1536


def test_audio_pipeline_state(rsm):
    rsm.create_session("s1", "interview")
    rsm.set_stt_state("s1", STTState.LISTENING)
    rsm.set_tts_state("s1", TTSState.STREAMING)
    s = rsm.get_session("s1")
    assert s.stt_state == STTState.LISTENING
    assert s.tts_state == TTSState.STREAMING


def test_epoch(rsm):
    rsm.create_session("s1", "interview")
    assert rsm.advance_epoch("s1") == 1
    assert rsm.advance_epoch("s1") == 2


def test_snapshot(rsm):
    rsm.create_session("s1", "interview", user_id="u1")
    snap = rsm.snapshot("s1")
    assert snap["session_id"] == "s1"
    assert snap["user_id"] == "u1"
    assert "connection_state" in snap


def test_destroy_session(rsm):
    rsm.create_session("s1", "interview")
    rsm.destroy_session("s1")
    assert rsm.get_session("s1") is None
    assert "s1" not in rsm.list_active_sessions()
