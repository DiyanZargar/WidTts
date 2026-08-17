"""Tests for centralized model catalogs."""
from app.shared.constants.model_catalogs import (
    get_speech_models,
    DEEPGRAM_STT_MODELS,
    DEEPGRAM_TTS_MODELS,
    ELEVENLABS_FALLBACK_MODELS,
    ELEVENLABS_FALLBACK_VOICES,
    FISH_AUDIO_TTS_MODELS,
    FLUX_TO_AURA_MAP,
)


class TestGetSpeechModels:
    """Test the main catalog function for each provider."""

    def test_deepgram_returns_complete_structure(self):
        result = get_speech_models("deepgram")
        assert "stt" in result
        assert "stt_by_language" in result
        assert "tts" in result
        assert "tts_by_language" in result
        assert "languages" in result

    def test_deepgram_has_tts_voices(self):
        result = get_speech_models("deepgram")
        assert len(result["tts"]) > 90  # Aura-1 + Aura-2 + Flux voices

    def test_deepgram_has_stt_models(self):
        result = get_speech_models("deepgram")
        assert len(result["stt"]) > 0
        model_ids = [m["id"] for m in result["stt"]]
        assert "nova-3" in model_ids

    def test_deepgram_has_languages(self):
        result = get_speech_models("deepgram")
        assert len(result["languages"]) > 40
        lang_codes = [l["code"] for l in result["languages"]]
        assert "en" in lang_codes
        assert "es" in lang_codes
        assert "ar" in lang_codes

    def test_deepgram_tts_by_language_english(self):
        result = get_speech_models("deepgram")
        assert "en" in result["tts_by_language"]
        en_entry = result["tts_by_language"]["en"]
        assert "voices" in en_entry
        assert len(en_entry["voices"]) > 10

    def test_elevenlabs_returns_complete_structure(self):
        result = get_speech_models("elevenlabs")
        assert "stt" in result
        assert "tts" in result
        assert "languages" in result

    def test_elevenlabs_has_32_languages(self):
        result = get_speech_models("elevenlabs")
        assert len(result["languages"]) == 32

    def test_elevenlabs_has_tts_models(self):
        result = get_speech_models("elevenlabs")
        model_ids = [m["id"] for m in result["tts"]]
        assert "eleven_multilingual_v2" in model_ids
        assert "eleven_flash_v2_5" in model_ids

    def test_elevenlabs_has_stt_models(self):
        result = get_speech_models("elevenlabs")
        model_ids = [m["id"] for m in result["stt"]]
        assert "scribe_v1" in model_ids

    def test_fishaudio_returns_complete_structure(self):
        result = get_speech_models("fishaudio")
        assert "stt" in result
        assert "tts" in result
        assert "languages" in result
        assert "tts_by_language" in result

    def test_fishaudio_has_no_stt(self):
        result = get_speech_models("fishaudio")
        assert result["stt"] == []
        assert result["stt_by_language"] == {}

    def test_fishaudio_has_tts_models(self):
        result = get_speech_models("fishaudio")
        model_ids = [m["id"] for m in result["tts"]]
        assert "s2.1-pro" in model_ids

    def test_fishaudio_has_many_languages(self):
        result = get_speech_models("fishaudio")
        assert len(result["languages"]) > 60

    def test_unknown_provider_returns_empty(self):
        result = get_speech_models("unknown")
        assert result["stt"] == []
        assert result["tts"] == []
        assert result["languages"] == []


class TestFallbackLists:
    def test_deepgram_stt_models_not_empty(self):
        assert len(DEEPGRAM_STT_MODELS) > 0

    def test_deepgram_tts_models_not_empty(self):
        assert len(DEEPGRAM_TTS_MODELS) > 0

    def test_elevenlabs_fallback_models_not_empty(self):
        assert len(ELEVENLABS_FALLBACK_MODELS) > 0

    def test_elevenlabs_fallback_voices_not_empty(self):
        assert len(ELEVENLABS_FALLBACK_VOICES) > 0

    def test_fish_audio_models_not_empty(self):
        assert len(FISH_AUDIO_TTS_MODELS) > 0

    def test_deepgram_stt_has_required_fields(self):
        for model in DEEPGRAM_STT_MODELS:
            assert "id" in model
            assert "name" in model

    def test_elevenlabs_voices_have_required_fields(self):
        for voice in ELEVENLABS_FALLBACK_VOICES:
            assert "id" in voice
            assert "name" in voice


class TestFluxToAuraMap:
    def test_contains_known_flux_models(self):
        assert "flux-rufus-en" in FLUX_TO_AURA_MAP
        assert "flux-aura-en" in FLUX_TO_AURA_MAP
        assert "flux-luna-en" in FLUX_TO_AURA_MAP

    def test_maps_to_aura_models(self):
        for flux, aura in FLUX_TO_AURA_MAP.items():
            assert flux.startswith("flux-"), f"Key {flux} is not a flux model"
            assert aura.startswith("aura-"), f"Value {aura} is not an aura model"

    def test_rufus_maps_to_orion(self):
        assert FLUX_TO_AURA_MAP["flux-rufus-en"] == "aura-orion-en"

    def test_aura_maps_to_asteria(self):
        assert FLUX_TO_AURA_MAP["flux-aura-en"] == "aura-asteria-en"
