import pytest
from app.modules.conversation.domain.policy.conversation_policy import ConversationPolicy, PolicyAction


@pytest.fixture
def policy():
    return ConversationPolicy(max_retries=3)


def test_stop_commands(policy):
    for cmd in ["stop", "stop talking", "be quiet", "pause", "quiet"]:
        result = policy.resolve_action("ANSWER", cmd)
        assert result["action"] == PolicyAction.STOP


def test_end_commands(policy):
    for cmd in ["end", "end conversation", "start over", "reset", "quit", "i'm done", "goodbye"]:
        result = policy.resolve_action("ANSWER", cmd)
        assert result["action"] == PolicyAction.END_CONVERSATION


def test_repeat_commands(policy):
    for cmd in ["repeat", "say that again", "pardon"]:
        result = policy.resolve_action("ANSWER", cmd)
        assert result["action"] == PolicyAction.REPEAT


def test_classification_routing(policy):
    assert policy.resolve_action("STOP", "blah")["action"] == PolicyAction.STOP
    assert policy.resolve_action("REPEAT", "blah")["action"] == PolicyAction.REPEAT
    assert policy.resolve_action("CORRECTION", "blah")["action"] == PolicyAction.CORRECTION
    assert policy.resolve_action("ANSWER", "blah")["action"] == PolicyAction.ANSWER
    assert policy.resolve_action("END_CONVERSATION", "blah")["action"] == PolicyAction.END_CONVERSATION


def test_evaluate_retry_passed(policy):
    result = policy.evaluate_retry(current_retry_count=1, validation_passed=True)
    assert result["should_advance"] is True
    assert result["max_retries_exceeded"] is False


def test_evaluate_retry_max_exceeded(policy):
    result = policy.evaluate_retry(current_retry_count=3, validation_passed=False)
    assert result["max_retries_exceeded"] is True
    assert result["should_advance"] is True


def test_evaluate_retry_normal(policy):
    result = policy.evaluate_retry(current_retry_count=1, validation_passed=False)
    assert result["should_advance"] is False
    assert result["max_retries_exceeded"] is False
    assert result["retry_increment"] == 1


def test_urgent_interruption_words():
    from app.shared.config.knobs import knobs
    urgent = knobs.policy.urgent_interruption_words
    for word in ["wait", "stop", "no", "no no", "hold on", "hang on", "pause", "one sec"]:
        assert word in urgent
