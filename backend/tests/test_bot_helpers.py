"""Tests for bot route helper functions."""
import pytest
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
