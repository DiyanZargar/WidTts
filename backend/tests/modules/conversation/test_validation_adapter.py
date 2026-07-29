import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.modules.conversation.infrastructure.external.litellm_validation_adapter import LiteLLMValidationAdapter


# ==============================================================================
# Layer 1 — Deterministic Guard Tests (no LLM needed)
# ==============================================================================

@pytest.mark.asyncio
async def test_deterministic_empty_response_rejected():
    adapter = LiteLLMValidationAdapter()
    res = await adapter.validate("question", "What did you eat?", "food or meal items", "")
    assert res["should_advance"] is False
    assert res["classification"] == "SYSTEM_ERROR"


@pytest.mark.asyncio
async def test_single_char_goes_to_llm():
    """With guards removed, 'x' goes to LLM — mock as rejected."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        json.dumps({"understood_intent": "Noise", "answered": False, "classification": "SYSTEM_ERROR",
                     "relevance": 0.0, "completeness": 0.0, "missing_information": ["Unintelligible."],
                     "should_repeat_question": True, "should_follow_up": False,
                     "follow_up_question": None, "should_advance": False, "reasoning": "Single letter"})
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate("question", "What did you eat?", "food or meal items", "x")
    assert res["should_advance"] is False
    assert res["classification"] == "SYSTEM_ERROR"


@pytest.mark.asyncio
async def test_single_char_i_accepted():
    """With guards removed, 'I' goes to LLM — mock it as accepted."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        json.dumps({"understood_intent": "Name", "answered": True, "classification": "FULLY_ANSWERED",
                     "relevance": 0.9, "completeness": 0.9, "missing_information": [],
                     "should_repeat_question": False, "should_follow_up": False,
                     "follow_up_question": None, "should_advance": True, "reasoning": "Valid name"})
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate("question", "What should I call you?", "a name", "I")
    assert res["should_advance"] is True


@pytest.mark.asyncio
async def test_single_digit_accepted():
    """With guards removed, '7' goes to LLM — mock it as accepted."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        json.dumps({"understood_intent": "Time", "answered": True, "classification": "FULLY_ANSWERED",
                     "relevance": 0.9, "completeness": 0.8, "missing_information": [],
                     "should_repeat_question": False, "should_follow_up": False,
                     "follow_up_question": None, "should_advance": True, "reasoning": "Valid time"})
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate("question", "What time did you wake up?", "a wake-up time", "7")
    assert res["should_advance"] is True


@pytest.mark.asyncio
async def test_dangling_fragment_goes_to_llm():
    """With guards removed, 'I was going to' goes to LLM — mock as accepted."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        json.dumps({"understood_intent": "Partial answer", "answered": True, "classification": "PARTIALLY_ANSWERED",
                     "relevance": 0.6, "completeness": 0.4, "missing_information": [],
                     "should_repeat_question": False, "should_follow_up": False,
                     "follow_up_question": None, "should_advance": True, "reasoning": "Partial"})
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate("question", "What did you eat?", "food or meal items", "I was going to")
    assert res["should_advance"] is True


@pytest.mark.asyncio
async def test_dangling_conjunction_goes_to_llm():
    """With guards removed, 'I woke up because' goes to LLM — mock as accepted."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        json.dumps({"understood_intent": "Partial answer", "answered": True, "classification": "PARTIALLY_ANSWERED",
                     "relevance": 0.5, "completeness": 0.3, "missing_information": [],
                     "should_repeat_question": False, "should_follow_up": False,
                     "follow_up_question": None, "should_advance": True, "reasoning": "Partial"})
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate("question", "What time did you wake up?", "a wake-up time", "I woke up because")
    assert res["should_advance"] is True


# ==============================================================================
# Layer 2 — LLM Semantic Validation Tests (mock LLM)
# ==============================================================================

def _mock_llm_response(json_body: str):
    """Create a mock OpenAI chat completion response."""
    mock_msg = MagicMock()
    mock_msg.content = json_body
    mock_msg.reasoning_content = None
    mock_choice = MagicMock()
    mock_choice.message = mock_msg
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


def _fully_answered_json(intent: str = "User answered the question."):
    return (
        '{"understood_intent": "' + intent + '", '
        '"answered": true, "classification": "FULLY_ANSWERED", '
        '"relevance": 1.0, "completeness": 1.0, "missing_information": [], '
        '"should_repeat_question": false, "should_follow_up": false, '
        '"follow_up_question": null, "should_advance": true, '
        '"reasoning": "The user clearly answered the question."}'
    )


def _off_topic_json(intent: str = "User spoke about something unrelated."):
    return (
        '{"understood_intent": "' + intent + '", '
        '"answered": false, "classification": "OFF_TOPIC", '
        '"relevance": 0.1, "completeness": 0.0, "missing_information": ["Relevant answer"], '
        '"should_repeat_question": true, "should_follow_up": false, '
        '"follow_up_question": null, "should_advance": false, '
        '"reasoning": "The response does not answer the question."}'
    )


def _needs_clarification_json(follow_up: str = "Could you tell me more?"):
    return (
        '{"understood_intent": "User gave a vague response.", '
        '"answered": false, "classification": "NEEDS_CLARIFICATION", '
        '"relevance": 0.3, "completeness": 0.2, "missing_information": ["More detail"], '
        '"should_repeat_question": false, "should_follow_up": true, '
        '"follow_up_question": "' + follow_up + '", "should_advance": false, '
        '"reasoning": "The response needs clarification."}'
    )


def _user_does_not_know_json():
    return (
        '{"understood_intent": "User does not know the answer.", '
        '"answered": false, "classification": "USER_DOES_NOT_KNOW", '
        '"relevance": 0.0, "completeness": 0.0, "missing_information": ["Answer to question"], '
        '"should_repeat_question": true, "should_follow_up": false, '
        '"follow_up_question": null, "should_advance": false, '
        '"reasoning": "User explicitly stated they do not know."}'
    )


@pytest.mark.asyncio
async def test_llm_time_answer_seven_advances():
    """THE BUG FIX: 'I woke up at seven.' must be accepted."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _fully_answered_json("User said they woke up at seven.")
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What time did you wake up today?", "a wake-up time", "I woke up at seven."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True
    assert res["classification"] == "FULLY_ANSWERED"


@pytest.mark.asyncio
async def test_llm_time_answer_around_seven_advances():
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _fully_answered_json("User said around seven.")
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What time did you wake up today?", "a wake-up time", "Around seven."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True


@pytest.mark.asyncio
async def test_llm_time_answer_half_past_seven_advances():
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _fully_answered_json("User said half past seven.")
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What time did you wake up today?", "a wake-up time", "Half past seven."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True


@pytest.mark.asyncio
async def test_llm_off_topic_brushed_teeth_rejected():
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _off_topic_json("User talked about brushing teeth, not wake-up time.")
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What time did you wake up?", "wake up time or hour", "I brushed my teeth."
        )
    assert res["should_advance"] is False
    assert res["valid"] is False


@pytest.mark.asyncio
async def test_llm_dont_know_accepted():
    """'I don't know' now advances — the system moves on instead of retrying."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _user_does_not_know_json()
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What city do you live in?", "city or location name", "I don't know."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True


@pytest.mark.asyncio
async def test_llm_yes_no_to_open_ended_accepted():
    """'Yes' to 'What did you eat?' now advances — voice answers are brief."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _needs_clarification_json("What did you eat?")
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What did you eat?", "food or meal items", "Yes"
        )
    assert res["should_advance"] is True
    assert res["valid"] is True


@pytest.mark.asyncio
async def test_llm_complete_answer_advances():
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _fully_answered_json("User ate toast.")
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What did you eat?", "food or meal items", "I ate toast."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True


@pytest.mark.asyncio
async def test_llm_favorite_color_advances():
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _fully_answered_json("User said blue.")
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What is your favorite color?", "favorite color name", "Blue."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True


@pytest.mark.asyncio
async def test_llm_binary_yes_no_advances():
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _fully_answered_json("User confirmed yes.")
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "Did you sleep well?", "yes or no confirmation of sleep quality", "Yes. I did."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True


@pytest.mark.asyncio
async def test_llm_stt_typo_understanding():
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        '{"understood_intent": "User learned something new recently.", '
        '"answered": true, "classification": "PARTIALLY_ANSWERED", '
        '"relevance": 0.8, "completeness": 0.5, "missing_information": ["What was learned"], '
        '"should_repeat_question": false, "should_follow_up": true, '
        '"follow_up_question": "What did you learn?", "should_advance": false, '
        '"reasoning": "User confirmed learning but did not specify what."}'
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question",
            "Have you learned something new recently?",
            "learning confirmation",
            "Yes. I have learned something near recently."
        )
    assert res["should_follow_up"] is True or res["classification"] in {"PARTIALLY_ANSWERED", "FULLY_ANSWERED"}
    assert "reason" in res


@pytest.mark.asyncio
async def test_llm_name_answer_advances():
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _fully_answered_json("User said their name is Alex.")
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What is your name?", "user name", "I'm Alex."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True


@pytest.mark.asyncio
async def test_llm_skipped_breakfast_advances():
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(return_value=_mock_llm_response(
        _fully_answered_json("User skipped breakfast.")
    ))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What did you eat?", "food or meal items", "I skipped breakfast."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True


# ==============================================================================
# Layer 3 — Graceful Degradation Tests (LLM unavailable)
# ==============================================================================

@pytest.mark.asyncio
async def test_fallback_multiword_advances_on_timeout():
    """When LLM times out, multi-word response that passed guards should advance."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(side_effect=asyncio.TimeoutError())
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What should I call you?", "user name or nickname", "Call me Alex."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True
    assert "fallback" in res["reasoning"].lower() or "degradation" in res["reasoning"].lower()


@pytest.mark.asyncio
async def test_fallback_single_word_asks_clarification():
    """When LLM times out, single-word response should ask for clarification."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(side_effect=asyncio.TimeoutError())
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What is your favorite color?", "favorite color name", "Blue."
        )
    assert res["should_advance"] is False
    assert res["classification"] == "NEEDS_CLARIFICATION"


@pytest.mark.asyncio
async def test_fallback_multiword_advances_on_exception():
    """When LLM throws any exception, multi-word response should still advance."""
    adapter = LiteLLMValidationAdapter()
    mock_create = AsyncMock(side_effect=ConnectionError("LLM proxy unreachable"))
    with patch.object(adapter, "_get_client") as mock_client:
        mock_client.return_value.chat.completions.create = mock_create
        res = await adapter.validate(
            "question", "What time did you wake up today?", "a wake-up time", "I woke up at seven."
        )
    assert res["should_advance"] is True
    assert res["valid"] is True
