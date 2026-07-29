import pytest
from unittest.mock import AsyncMock, MagicMock
from app.modules.interruption.application.use_cases.classify_interruption import ClassifyInterruption


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    return adapter


@pytest.fixture
def classifier(mock_adapter):
    return ClassifyInterruption(classifier_adapter=mock_adapter)


# ── Deterministic system commands (bypass LLM) ──

@pytest.mark.asyncio
async def test_deterministic_stop(classifier, mock_adapter):
    """'stop' is a deterministic system command — LLM is NOT called."""
    result = await classifier.execute("stop")
    assert result["type"] == "STOP"
    assert result["confidence"] == 1.0
    mock_adapter.classify.assert_not_called()


@pytest.mark.asyncio
async def test_deterministic_stop_variants(classifier, mock_adapter):
    for cmd in ["stop talking", "be quiet", "shut up", "pause"]:
        result = await classifier.execute(cmd)
        assert result["type"] == "STOP"
    mock_adapter.classify.assert_not_called()


@pytest.mark.asyncio
async def test_deterministic_end(classifier, mock_adapter):
    """'end conversation' is a deterministic system command."""
    result = await classifier.execute("end conversation")
    assert result["type"] == "END_CONVERSATION"
    assert result["confidence"] == 1.0
    mock_adapter.classify.assert_not_called()


@pytest.mark.asyncio
async def test_deterministic_end_variants(classifier, mock_adapter):
    for cmd in ["end", "start over", "reset", "quit", "i'm done"]:
        result = await classifier.execute(cmd)
        assert result["type"] == "END_CONVERSATION"
    mock_adapter.classify.assert_not_called()


# ── LLM-based semantic classification ──

@pytest.mark.asyncio
async def test_llm_answer(classifier, mock_adapter):
    """Normal answer to a question — LLM classifies as ANSWER."""
    mock_adapter.classify.return_value = {"interrupt": True, "type": "ANSWER", "confidence": 0.95}
    result = await classifier.execute(
        transcript="Seven",
        current_question="What time did you wake up?",
    )
    assert result["type"] == "ANSWER"
    mock_adapter.classify.assert_called_once()


@pytest.mark.asyncio
async def test_llm_repeat(classifier, mock_adapter):
    """User asks to repeat — LLM classifies as REPEAT."""
    mock_adapter.classify.return_value = {"interrupt": True, "type": "REPEAT", "confidence": 0.92}
    result = await classifier.execute(
        transcript="Can you repeat the question?",
        current_question="What time did you wake up?",
    )
    assert result["type"] == "REPEAT"


@pytest.mark.asyncio
async def test_llm_correction(classifier, mock_adapter):
    """User corrects a previous answer — LLM classifies as CORRECTION."""
    mock_adapter.classify.return_value = {"interrupt": True, "type": "CORRECTION", "confidence": 0.98}
    result = await classifier.execute(
        transcript="No, I meant Jonathan",
        current_question="What should I call you?",
        previous_answer="John",
    )
    assert result["type"] == "CORRECTION"


@pytest.mark.asyncio
async def test_llm_answer_during_tts(classifier, mock_adapter):
    """User answers while TTS is playing — LLM classifies as ANSWER."""
    mock_adapter.classify.return_value = {"interrupt": True, "type": "ANSWER", "confidence": 0.90}
    result = await classifier.execute(
        transcript="Seven",
        current_question="What time did you wake up?",
        tts_text="What time did you wake up today?",
        is_tts_playing=True,
    )
    assert result["type"] == "ANSWER"


@pytest.mark.asyncio
async def test_llm_none(classifier, mock_adapter):
    """Background noise — LLM classifies as NONE."""
    mock_adapter.classify.return_value = {"interrupt": False, "type": "NONE", "confidence": 0.1}
    result = await classifier.execute(transcript="um")
    assert result["type"] == "NONE"
    assert result["interrupt"] is False


# ── No adapter fallback ──

@pytest.mark.asyncio
async def test_no_adapter_defaults_to_none():
    """Without an adapter, classification defaults to NONE."""
    classifier = ClassifyInterruption(classifier_adapter=None)
    result = await classifier.execute(transcript="something random")
    assert result["type"] == "NONE"
    assert result["interrupt"] is False
