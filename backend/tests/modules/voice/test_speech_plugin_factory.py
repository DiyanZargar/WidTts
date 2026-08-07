"""Tests for SpeechPluginFactory module-level functions."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.modules.voice.infrastructure.external.speech_plugin_factory import (
    build_stt_plugin,
    build_tts_plugin,
    UnsupportedProviderError,
)


def _make_config(provider_type, **extra):
    """Build a minimal config dict with mocked encrypted credentials."""
    config = {
        "provider_type": provider_type,
        "credentials_enc": {"nonce": "test", "ciphertext": "test"},
        "key_version": 1,
    }
    config.update(extra)
    return config


@pytest.mark.asyncio
@patch("app.modules.voice.infrastructure.external.speech_plugin_factory._decrypt_credentials",
       new_callable=AsyncMock, return_value={"api_key": "test-key"})
async def test_build_stt_deepgram(mock_decrypt):
    from livekit.plugins import deepgram
    config = _make_config("deepgram", stt_model="nova-2")
    result = await build_stt_plugin(config)
    assert result is not None
    mock_decrypt.assert_called_once()


@pytest.mark.asyncio
@patch("app.modules.voice.infrastructure.external.speech_plugin_factory._decrypt_credentials",
       new_callable=AsyncMock, return_value={"api_key": "test-key"})
async def test_build_stt_elevenlabs(mock_decrypt):
    config = _make_config("elevenlabs", stt_model="scribe_v1")
    result = await build_stt_plugin(config)
    assert result is not None


@pytest.mark.asyncio
@patch("app.modules.voice.infrastructure.external.speech_plugin_factory._decrypt_credentials",
       new_callable=AsyncMock, return_value={"api_key": "test-key"})
async def test_build_stt_unknown_provider(mock_decrypt):
    config = _make_config("unknown_provider")
    with pytest.raises(UnsupportedProviderError):
        await build_stt_plugin(config)


@pytest.mark.asyncio
@patch("app.modules.voice.infrastructure.external.speech_plugin_factory._decrypt_credentials",
       new_callable=AsyncMock, return_value={"api_key": "test-key"})
async def test_build_tts_deepgram(mock_decrypt):
    config = _make_config("deepgram", tts_model="aura-asteria-en")
    result = await build_tts_plugin(config)
    assert result is not None


@pytest.mark.asyncio
@patch("app.modules.voice.infrastructure.external.speech_plugin_factory._decrypt_credentials",
       new_callable=AsyncMock, return_value={"api_key": "test-key"})
async def test_build_tts_elevenlabs(mock_decrypt):
    config = _make_config("elevenlabs", tts_voice_id="test-voice-id")
    result = await build_tts_plugin(config)
    assert result is not None


@pytest.mark.asyncio
@patch("app.modules.voice.infrastructure.external.speech_plugin_factory._decrypt_credentials",
       new_callable=AsyncMock, return_value={"api_key": "test-key"})
async def test_build_tts_elevenlabs_no_voice_id(mock_decrypt):
    config = _make_config("elevenlabs", tts_voice_id="")
    with pytest.raises(ValueError, match="tts_voice_id"):
        await build_tts_plugin(config)


@pytest.mark.asyncio
@patch("app.modules.voice.infrastructure.external.speech_plugin_factory._decrypt_credentials",
       new_callable=AsyncMock, return_value={"api_key": "test-key"})
async def test_build_tts_unknown_provider(mock_decrypt):
    config = _make_config("unknown_provider")
    with pytest.raises(UnsupportedProviderError):
        await build_tts_plugin(config)
