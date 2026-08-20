"""Unit tests for the modular BaseSpeechProvider strategy implementations."""

import pytest
from unittest.mock import patch, MagicMock

from app.modules.voice.infrastructure.providers.base import (
    BaseSpeechProvider,
    UnsupportedProviderError,
    mask,
    mask_credentials,
)
from app.modules.voice.infrastructure.providers.deepgram_provider import DeepgramProvider
from app.modules.voice.infrastructure.providers.elevenlabs_provider import ElevenLabsProvider
from app.modules.voice.infrastructure.providers.fish_audio_provider import FishAudioProvider, FishAudioTTS


class TestBaseSpeechProviderContracts:
    def test_mask_function(self):
        assert mask("") == "****"
        assert mask("123") == "****"
        assert mask("12345678", visible=4) == "1234…(len=8)"

    def test_mask_credentials_dict(self):
        creds = {"api_key": "sk-secret-key", "token": "abc"}
        masked = mask_credentials(creds)
        assert masked["api_key"] == "sk-s…(len=13)"
        assert masked["token"] == "****"


class TestDeepgramProviderStrategy:
    @patch("livekit.plugins.deepgram.STT")
    def test_build_stt(self, mock_stt):
        provider = DeepgramProvider()
        config = {"stt_model": "nova-3", "stt_language": "en"}
        creds = {"api_key": "dg-key"}
        provider.build_stt(config, creds)
        mock_stt.assert_called_once()
        kwargs = mock_stt.call_args.kwargs
        assert kwargs["api_key"] == "dg-key"
        assert kwargs["model"] == "nova-3"
        assert kwargs["language"] == "en-US"

    @patch("livekit.plugins.deepgram.TTS")
    def test_build_tts_flux_mapping(self, mock_tts):
        provider = DeepgramProvider()
        config = {"tts_model": "flux-rufus-en"}
        creds = {"api_key": "dg-key"}
        provider.build_tts(config, creds)
        mock_tts.assert_called_once()
        kwargs = mock_tts.call_args.kwargs
        assert kwargs["api_key"] == "dg-key"
        assert kwargs["model"] == "aura-orion-en"
        assert kwargs["sample_rate"] == 24000
        assert kwargs["encoding"] == "linear16"


class TestElevenLabsProviderStrategy:
    @patch("livekit.plugins.elevenlabs.STT")
    def test_build_stt(self, mock_stt):
        provider = ElevenLabsProvider()
        config = {"stt_model": "scribe_v1", "stt_language": "es"}
        creds = {"api_key": "el-key"}
        provider.build_stt(config, creds)
        mock_stt.assert_called_once_with(api_key="el-key", model_id="scribe_v1", language_code="es")

    @patch("livekit.plugins.elevenlabs.TTS")
    def test_build_tts_default_voice(self, mock_tts):
        provider = ElevenLabsProvider()
        config = {}
        creds = {"api_key": "el-key"}
        provider.build_tts(config, creds)
        mock_tts.assert_called_once()
        kwargs = mock_tts.call_args.kwargs
        assert kwargs["api_key"] == "el-key"
        assert kwargs["voice_id"] == "EXAVITQu4vr4xnSDxMaL"
        assert kwargs["model"] == "eleven_turbo_v2_5"
        assert kwargs["auto_mode"] is True


class TestFishAudioProviderStrategy:
    def test_build_stt_raises_unsupported(self):
        provider = FishAudioProvider()
        with pytest.raises(UnsupportedProviderError):
            provider.build_stt({}, {"api_key": "fa-key"})

    def test_build_tts_constructs_fish_audio_instance(self):
        provider = FishAudioProvider()
        config = {"tts_model": "s2.1-pro", "tts_custom_voice_id": "1234567890abcdef12345678"}
        creds = {"api_key": "fa-key"}
        tts = provider.build_tts(config, creds)
        assert isinstance(tts, FishAudioTTS)
        assert tts.model == "s2.1-pro"
