import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from main import app
from app.shared.config.settings import settings
from app.shared.security.token_service import create_token


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_integration.db")
    monkeypatch.setattr(settings, "database_path", db_path)
    from app.shared.database.init_db import init_db
    init_db()
    yield db_path


def _send_tts_end(ws):
    """Helper: send a tts_end JSON message to unblock backend speak()."""
    ws.send_text(json.dumps({"type": "tts_end"}))


@patch("app.modules.voice.infrastructure.external.deepgram_stt_adapter.DeepgramSTTAdapter.connect", new_callable=AsyncMock)
@patch("app.modules.voice.infrastructure.external.deepgram_stt_adapter.DeepgramSTTAdapter.close", new_callable=AsyncMock)
@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.DeepgramTTSAdapter.connect_stream", new_callable=AsyncMock)
@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.DeepgramTTSAdapter.synthesize_stream")
@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.DeepgramTTSAdapter.close", new_callable=AsyncMock)
def test_websocket_initial_connection_and_session_started(mock_tts_close, mock_stream, mock_connect_stream, mock_stt_close, mock_stt_connect):
    async def _fake_gen():
        yield b"fake_audio_bytes"
    mock_stream.side_effect = lambda *args, **kwargs: _fake_gen()
    client = TestClient(app)
    user_token = create_token("user_test_101")

    with client.websocket_connect(f"/ws/daily_life_companion?token={user_token}") as websocket:
        # Event 1: session_started
        evt1 = websocket.receive_json()
        assert evt1["event"] == "session_started"
        assert "session_id" in evt1["payload"]
        assert evt1["payload"]["user_id"] == "user_test_101"
        assert evt1["payload"]["is_recovery"] is False

        # Event 2: tts_audio_meta for intro line
        evt2 = websocket.receive_json()
        assert evt2["event"] == "tts_audio_meta"
        assert evt2["payload"].get("is_streaming") is True

        # Send tts_end BEFORE receiving audio bytes so the backend
        # event loop processes it while speak() is still awaiting.
        _send_tts_end(websocket)

        # Binary audio bytes (still arrives in order)
        audio_frame = websocket.receive_bytes()
        assert audio_frame == b"fake_audio_bytes"

        # Stream end event
        evt_end = websocket.receive_json()
        assert evt_end["event"] == "tts_stream_end"

        # Event 3: question event for sequence 0
        evt3 = websocket.receive_json()
        assert evt3["event"] == "question"
        assert evt3["payload"]["sequence"] == 0

        # Event 4: tts_audio_meta for question 0
        evt4 = websocket.receive_json()
        assert evt4["event"] == "tts_audio_meta"

        # Unblock question TTS
        _send_tts_end(websocket)

        # Binary audio bytes for question 0
        audio_frame2 = websocket.receive_bytes()
        assert audio_frame2 == b"fake_audio_bytes"

        # Stream end event for question
        evt_end2 = websocket.receive_json()
        assert evt_end2["event"] == "tts_stream_end"


@patch("app.modules.voice.infrastructure.external.deepgram_stt_adapter.DeepgramSTTAdapter.connect", new_callable=AsyncMock)
@patch("app.modules.voice.infrastructure.external.deepgram_stt_adapter.DeepgramSTTAdapter.close", new_callable=AsyncMock)
@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.DeepgramTTSAdapter.connect_stream", new_callable=AsyncMock)
@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.DeepgramTTSAdapter.synthesize_stream")
@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.DeepgramTTSAdapter.close", new_callable=AsyncMock)
def test_authorized_session_recovery(mock_tts_close, mock_stream, mock_connect_stream, mock_stt_close, mock_stt_connect):
    async def _fake_gen():
        yield b"fake_audio_bytes"
    mock_stream.side_effect = lambda *args, **kwargs: _fake_gen()
    client = TestClient(app)
    user_token = create_token("user_owner_404")

    # Step 1: Connect and create session
    with client.websocket_connect(f"/ws/daily_life_companion?token={user_token}") as websocket:
        evt = websocket.receive_json()
        session_id = evt["payload"]["session_id"]
        websocket.receive_json()  # intro tts meta
        _send_tts_end(websocket)  # confirm intro done
        websocket.receive_bytes()  # intro audio
        websocket.receive_json()  # intro stream end
        websocket.receive_json()  # question 0
        websocket.receive_json()  # question 0 tts meta
        _send_tts_end(websocket)  # confirm question 0 done
        websocket.receive_bytes()  # question 0 audio
        websocket.receive_json()  # question 0 stream end

    # Step 2: Reconnect as same user (Authorized session recovery)
    with client.websocket_connect(f"/ws/daily_life_companion?session_id={session_id}&token={user_token}") as websocket:
        evt_start = websocket.receive_json()
        assert evt_start["event"] == "session_started"
        assert evt_start["payload"]["is_recovery"] is True

        evt_rec = websocket.receive_json()
        assert evt_rec["event"] == "transcript_recovery"
        assert isinstance(evt_rec["payload"]["messages"], list)


@patch("app.modules.voice.infrastructure.external.deepgram_stt_adapter.DeepgramSTTAdapter.connect", new_callable=AsyncMock)
@patch("app.modules.voice.infrastructure.external.deepgram_stt_adapter.DeepgramSTTAdapter.close", new_callable=AsyncMock)
@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.DeepgramTTSAdapter.connect_stream", new_callable=AsyncMock)
@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.DeepgramTTSAdapter.synthesize_stream")
@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.DeepgramTTSAdapter.close", new_callable=AsyncMock)
def test_unauthorized_session_recovery_rejection(mock_tts_close, mock_stream, mock_connect_stream, mock_stt_close, mock_stt_connect):
    async def _fake_gen():
        yield b"fake_audio_bytes"
    mock_stream.side_effect = lambda *args, **kwargs: _fake_gen()
    client = TestClient(app)
    owner_token = create_token("user_owner_999")
    attacker_token = create_token("user_attacker_000")

    # Step 1: Owner creates session
    with client.websocket_connect(f"/ws/daily_life_companion?token={owner_token}") as websocket:
        evt = websocket.receive_json()
        session_id = evt["payload"]["session_id"]

    # Step 2: Attacker attempts to recover owner's session_id
    with client.websocket_connect(f"/ws/daily_life_companion?session_id={session_id}&token={attacker_token}") as websocket:
        evt_err = websocket.receive_json()
        assert evt_err["event"] == "error"
        assert "unauthorized" in evt_err["payload"]["message"].lower()


def test_invalid_token_authentication_failure():
    client = TestClient(app)
    invalid_token = "invalid.malformed.token.string"

    with client.websocket_connect(f"/ws/daily_life_companion?token={invalid_token}") as websocket:
        evt_err = websocket.receive_json()
        assert evt_err["event"] == "error"
        assert "authentication failed" in evt_err["payload"]["message"].lower()
