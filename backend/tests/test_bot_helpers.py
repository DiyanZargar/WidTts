"""Tests for bot route helper functions."""
from app.entrypoints.http.admin.bot_routes import _generate_slug


class TestGenerateSlug:
    def test_simple_name(self):
        assert _generate_slug("My Bot") == "my-bot"

    def test_name_with_special_chars(self):
        assert _generate_slug("Bot #1 (v2)!") == "bot-1-v2"

    def test_name_with_multiple_spaces(self):
        assert _generate_slug("My   Bot   Name") == "my-bot-name"

    def test_name_with_leading_trailing_spaces(self):
        assert _generate_slug("  My Bot  ") == "my-bot"

    def test_empty_name_fallback(self):
        assert _generate_slug("") == "bot"

    def test_only_special_chars_fallback(self):
        assert _generate_slug("!!!") == "bot"

    def test_name_with_unicode(self):
        result = _generate_slug("Bot Español")
        # Should produce valid slug-like output
        assert result  # non-empty
        assert " " not in result  # no spaces

    def test_name_with_numbers(self):
        assert _generate_slug("Bot 2024") == "bot-2024"

    def test_name_already_slug(self):
        assert _generate_slug("my-bot-name") == "my-bot-name"

    def test_single_word(self):
        assert _generate_slug("Assistant") == "assistant"

    def test_name_with_underscores(self):
        assert _generate_slug("my_bot_name") == "my-bot-name"

    def test_consecutive_dashes_stripped(self):
        result = _generate_slug("bot---name")
        assert "--" not in result


class TestBotRequestSchemas:
    def test_bot_create_request_preserves_custom_tts_and_greeting(self):
        from app.entrypoints.http.admin.bot_routes import BotCreateRequest
        data = {
            "name": "Custom Assistant",
            "greeting": "Hello, I am your assistant!",
            "tts_custom_model": "s2.1-pro",
            "tts_custom_voice_id": "78326a284931481283726154",
            "tts_custom_endpoint": "https://api.fish.audio",
        }
        req = BotCreateRequest(**data)
        dump = req.model_dump()
        assert dump["greeting"] == "Hello, I am your assistant!"
        assert dump["tts_custom_model"] == "s2.1-pro"
        assert dump["tts_custom_voice_id"] == "78326a284931481283726154"
        assert dump["tts_custom_endpoint"] == "https://api.fish.audio"

    def test_bot_update_request_preserves_custom_tts_and_greeting(self):
        from app.entrypoints.http.admin.bot_routes import BotUpdateRequest
        data = {
            "greeting": "Updated greeting!",
            "tts_custom_model": "s2-pro",
            "tts_custom_voice_id": "custom_voice_123",
            "tts_custom_endpoint": "https://custom.endpoint",
        }
        req = BotUpdateRequest(**data)
        dump = req.model_dump()
        assert dump["greeting"] == "Updated greeting!"
        assert dump["tts_custom_model"] == "s2-pro"
        assert dump["tts_custom_voice_id"] == "custom_voice_123"
        assert dump["tts_custom_endpoint"] == "https://custom.endpoint"
