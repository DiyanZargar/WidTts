"""Integration tests for LiveKitSession lifecycle."""
import pytest
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock

from app.modules.voice.infrastructure.external.livekit_session_adapter import (
    SessionSnapshot,
    LiveKitSession,
)


def _make_snapshot(**overrides):
    defaults = {
        "session_id": "test-session-1",
        "bot_id": "bot-1",
        "bot_name": "Test Bot",
        "system_prompt": "You are a test assistant.",
        "speech_provider_type": "deepgram",
        "stt_model": "nova-2",
        "tts_model": "aura-asteria-en",
        "tts_voice_id": "",
        "llm_provider_id": "openai",
        "llm_model": "gpt-4o-mini",
        "server_url": "ws://localhost:7880",
        "room_name": "test-room",
        "audio_sample_rate": 16000,
    }
    defaults.update(overrides)
    return SessionSnapshot(**defaults)


def test_session_snapshot_creation():
    snap = _make_snapshot()
    assert snap.session_id == "test-session-1"
    assert snap.bot_name == "Test Bot"
    assert snap.system_prompt == "You are a test assistant."


def test_session_snapshot_has_credential_fields():
    snap = _make_snapshot(
        encrypted_speech_credentials={"nonce": "abc", "ciphertext": "def"},
        speech_key_version=1,
    )
    assert snap.encrypted_speech_credentials == {"nonce": "abc", "ciphertext": "def"}
    assert snap.speech_key_version == 1


def test_session_snapshot_has_llm_credentials():
    snap = _make_snapshot(llm_api_key="sk-test", llm_base_url="https://api.example.com/v1")
    assert snap.llm_api_key == "sk-test"
    assert snap.llm_base_url == "https://api.example.com/v1"


def test_livekit_session_not_destroyed_initially():
    snap = _make_snapshot()
    session = LiveKitSession(snapshot=snap)
    assert session.is_destroyed is False


@pytest.mark.asyncio
async def test_livekit_session_destroy_idempotent():
    snap = _make_snapshot()
    session = LiveKitSession(snapshot=snap)
    await session.destroy()
    assert session.is_destroyed is True
    # Second destroy should not raise
    await session.destroy()
    assert session.is_destroyed is True


@pytest.mark.asyncio
async def test_livekit_session_destroy_clears_refs():
    snap = _make_snapshot()
    session = LiveKitSession(snapshot=snap)
    session._stt_plugin = MagicMock()
    session._tts_plugin = MagicMock()
    session._vad_plugin = MagicMock()

    await session.destroy()

    assert session._stt_plugin is None
    assert session._tts_plugin is None
    assert session._vad_plugin is None
    assert session._llm_bridge is None
    assert session._room is None
