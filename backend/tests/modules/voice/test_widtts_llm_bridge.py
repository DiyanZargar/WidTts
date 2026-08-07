"""Tests for WidTTSLLMBridge and its helpers."""
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.modules.voice.infrastructure.external.widtts_llm_bridge import (
    WidTTSLLMBridge,
    DefaultConversationAdapter,
    _extract_user_text,
    _find_last_assistant_message,
    _STOP_ACK,
    _END_ACK,
)
from app.modules.conversation.domain.policy.conversation_policy import PolicyAction


class MockChatItem:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockChatContext:
    def __init__(self, items):
        self.items = items


def test_bridge_initialization():
    adapter = MagicMock()
    policy = MagicMock()
    bot = {"system_prompt": "You are helpful", "model": "gpt-4o-mini", "api_key": "test", "base_url": ""}
    bridge = WidTTSLLMBridge(bot=bot, conversation_adapter=adapter, policy=policy)
    assert bridge._system_prompt == "You are helpful"
    assert bridge._adapter is adapter
    assert bridge._policy is policy


def test_bridge_model_property():
    adapter = MagicMock()
    policy = MagicMock()
    bot = {"system_prompt": "", "model": "gpt-4o", "api_key": "", "base_url": ""}
    bridge = WidTTSLLMBridge(bot=bot, conversation_adapter=adapter, policy=policy)
    assert bridge.model == "gpt-4o"


def test_bridge_provider_property():
    adapter = MagicMock()
    policy = MagicMock()
    bot = {"system_prompt": "", "model": "gpt-4o", "api_key": "", "base_url": ""}
    bridge = WidTTSLLMBridge(bot=bot, conversation_adapter=adapter, policy=policy)
    assert bridge.provider == "widtts"


def test_extract_user_text():
    ctx = MockChatContext([
        MockChatItem("system", "You are helpful"),
        MockChatItem("user", "Hello there"),
        MockChatItem("assistant", "Hi!"),
        MockChatItem("user", "How are you?"),
    ])
    assert _extract_user_text(ctx) == "How are you?"


def test_extract_user_text_empty():
    ctx = MockChatContext([])
    assert _extract_user_text(ctx) == ""


def test_extract_user_text_no_user():
    ctx = MockChatContext([MockChatItem("system", "You are helpful")])
    assert _extract_user_text(ctx) == ""


def test_extract_user_text_list_content():
    item = MockChatItem("user", [MagicMock(text="Hello"), MagicMock(text="world")])
    ctx = MockChatContext([item])
    assert _extract_user_text(ctx) == "Hello world"


def test_find_last_assistant_message():
    ctx = MockChatContext([
        MockChatItem("user", "Hello"),
        MockChatItem("assistant", "Hi there!"),
        MockChatItem("user", "How are you?"),
        MockChatItem("assistant", "I'm good, thanks!"),
    ])
    assert _find_last_assistant_message(ctx) == "I'm good, thanks!"


def test_find_last_assistant_message_none():
    ctx = MockChatContext([MockChatItem("user", "Hello")])
    assert _find_last_assistant_message(ctx) is None


def test_llm_config_from_bot():
    adapter = MagicMock()
    policy = MagicMock()
    bot = {
        "system_prompt": "test prompt",
        "model": "gpt-4o",
        "api_key": "sk-test",
        "base_url": "https://api.example.com/v1",
    }
    bridge = WidTTSLLMBridge(bot=bot, conversation_adapter=adapter, policy=policy)
    assert bridge._llm_config["api_key"] == "sk-test"
    assert bridge._llm_config["base_url"] == "https://api.example.com/v1"
    assert bridge._llm_config["model"] == "gpt-4o"
