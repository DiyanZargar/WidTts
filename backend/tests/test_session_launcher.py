"""Tests for voice profile detection in session_launcher.py.

Fish Audio voice profiles are 24-char hex (MongoDB ObjectIds).
ElevenLabs voice profiles are 20-char alphanumeric (not starting with eleven_/scribe_).
"""
import pytest
from app.modules.voice.application.session_launcher import detect_voice_profile


class TestFishAudioDetection:
    def test_valid_fish_audio_profile(self):
        vid, model = detect_voice_profile("abcdef1234567890abcdef12", "fishaudio")
        assert vid == "abcdef1234567890abcdef12"
        assert model == ""

    def test_valid_fish_audio_profile_uppercase(self):
        vid, model = detect_voice_profile("ABCDEF1234567890ABCDEF12", "fishaudio")
        assert vid == "ABCDEF1234567890ABCDEF12"
        assert model == ""

    def test_fish_audio_engine_model_not_detected_as_profile(self):
        vid, model = detect_voice_profile("s2.1-pro", "fishaudio")
        assert vid == ""
        assert model == "s2.1-pro"

    def test_fish_audio_short_string_not_profile(self):
        vid, model = detect_voice_profile("abcdef123456", "fishaudio")
        assert vid == ""
        assert model == "abcdef123456"

    def test_fish_audio_25_char_not_profile(self):
        vid, model = detect_voice_profile("a" * 25, "fishaudio")
        assert vid == ""
        assert model == "a" * 25

    def test_fish_audio_non_hex_not_profile(self):
        vid, model = detect_voice_profile("ghij" * 6, "fishaudio")
        assert vid == ""
        assert model == "ghij" * 6


class TestElevenLabsDetection:
    def test_valid_elevenlabs_profile(self):
        vid, model = detect_voice_profile("EXAVITQu4vr4xnSDxMaL", "elevenlabs")
        assert vid == "EXAVITQu4vr4xnSDxMaL"
        assert model == ""

    def test_elevenlabs_model_not_detected_as_profile(self):
        vid, model = detect_voice_profile("eleven_turbo_v2_5", "elevenlabs")
        assert vid == ""
        assert model == "eleven_turbo_v2_5"

    def test_elevenlabs_scribe_not_detected_as_profile(self):
        vid, model = detect_voice_profile("scribe_v1_abcdef12345", "elevenlabs")
        assert vid == ""
        assert model == "scribe_v1_abcdef12345"

    def test_elevenlabs_short_string_not_profile(self):
        vid, model = detect_voice_profile("abc123", "elevenlabs")
        assert vid == ""
        assert model == "abc123"

    def test_elevenlabs_with_spaces_not_profile(self):
        vid, model = detect_voice_profile("EXAVITQu4vr4xnSD MaL", "elevenlabs")
        assert vid == ""
        assert model == "EXAVITQu4vr4xnSD MaL"


class TestOtherProviders:
    def test_deepgram_model_passthrough(self):
        vid, model = detect_voice_profile("nova-3", "deepgram")
        assert vid == ""
        assert model == "nova-3"

    def test_deepgram_flux_passthrough(self):
        vid, model = detect_voice_profile("flux-rufus-en", "deepgram")
        assert vid == ""
        assert model == "flux-rufus-en"

    def test_empty_model(self):
        vid, model = detect_voice_profile("", "fishaudio")
        assert vid == ""
        assert model == ""

    def test_empty_provider(self):
        vid, model = detect_voice_profile("abcdef1234567890abcdef12", "")
        assert vid == ""
        assert model == "abcdef1234567890abcdef12"

    def test_none_values(self):
        vid, model = detect_voice_profile("", "")
        assert vid == ""
        assert model == ""
