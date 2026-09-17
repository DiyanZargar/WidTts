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
    def test_bot_create_request_preserves_greeting_and_fields(self):
        from app.entrypoints.http.admin.bot_routes import BotCreateRequest
        data = {
            "name": "Custom Assistant",
            "greeting": "Hello, I am your assistant!",
            "system_prompt": "You are a helpful assistant.",
            "stt_model": "nova-3",
            "tts_model": "flux-rufus-en",
        }
        req = BotCreateRequest(**data)
        dump = req.model_dump()
        assert dump["name"] == "Custom Assistant"
        assert dump["greeting"] == "Hello, I am your assistant!"
        assert dump["system_prompt"] == "You are a helpful assistant."
        assert dump["stt_model"] == "nova-3"
        assert dump["tts_model"] == "flux-rufus-en"
        assert "personality" not in dump
        assert "tts_custom_model" not in dump
        assert "tts_custom_voice_id" not in dump
        assert "tts_custom_endpoint" not in dump

    def test_bot_update_request_preserves_greeting_and_fields(self):
        from app.entrypoints.http.admin.bot_routes import BotUpdateRequest
        data = {
            "greeting": "Updated greeting!",
            "system_prompt": "Updated prompt",
        }
        req = BotUpdateRequest(**data)
        dump = req.model_dump(exclude_unset=True)
        assert dump["greeting"] == "Updated greeting!"
        assert dump["system_prompt"] == "Updated prompt"
        assert "personality" not in dump
        assert "tts_custom_model" not in dump
        assert "tts_custom_voice_id" not in dump
        assert "tts_custom_endpoint" not in dump

    def test_bot_response_schema_excludes_unused_fields(self):
        from app.shared.schemas import BotResponse
        raw_db_record = {
            "id": "bot-123",
            "name": "Maya",
            "description": "Receptionist",
            "personality": "friendly",
            "system_prompt": "You are Maya",
            "speech_provider_id": "sp-123",
            "name_locked": 1,
            "tts_custom_model": "custom-m",
            "tts_custom_voice_id": "custom-v",
            "tts_custom_endpoint": "http://custom",
            "is_active": 1,
            "is_deployed": 1,
            "deploy_slug": "maya",
        }
        resp = BotResponse(**raw_db_record)
        dump = resp.model_dump()
        assert dump["id"] == "bot-123"
        assert dump["name"] == "Maya"
        assert dump["system_prompt"] == "You are Maya"
        assert dump["is_active"] is True
        assert dump["is_deployed"] is True
        assert "personality" not in dump
        assert "tts_custom_model" not in dump
        assert "tts_custom_voice_id" not in dump
        assert "tts_custom_endpoint" not in dump
        assert "speech_provider_id" not in dump
        assert "name_locked" not in dump
