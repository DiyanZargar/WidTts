import pytest
from app.modules.conversation.application.services.context_manager import ContextManager


@pytest.fixture
def ctx():
    return ContextManager(max_tokens=100)


def test_add_and_get_history(ctx):
    ctx.add_message("sess-1", "system", "Hello")
    ctx.add_message("sess-1", "user", "Hi there")
    history = ctx.get_history("sess-1")
    assert len(history) == 2
    assert history[0].role == "system"
    assert history[1].content == "Hi there"


def test_get_recent(ctx):
    for i in range(15):
        ctx.add_message("sess-1", "user", f"msg{i}")
    recent = ctx.get_recent("sess-1", count=5)
    assert len(recent) == 5
    assert recent[-1].content == "msg14"


def test_pruning(ctx):
    # Each message ~20 chars = ~5 tokens; max=100 tokens = ~20 messages
    for i in range(30):
        ctx.add_message("sess-1", "user", "x" * 20)
    history = ctx.get_history("sess-1")
    assert len(history) < 30


def test_build_validation_prompt(ctx):
    ctx.add_message("sess-1", "system", "Welcome")
    ctx.add_message("sess-1", "user", "Hi")
    prompt = ctx.build_validation_prompt(
        "sess-1", "text", "Q1", "name", "My name is John"
    )
    assert "Q1" in prompt
    assert "My name is John" in prompt
    assert "###METADATA###" in prompt


def test_clear(ctx):
    ctx.add_message("sess-1", "user", "hello")
    ctx.clear("sess-1")
    assert ctx.get_history("sess-1") == []
