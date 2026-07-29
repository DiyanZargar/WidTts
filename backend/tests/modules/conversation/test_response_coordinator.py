import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.modules.conversation.application.services.response_coordinator import ResponseCoordinator, StreamingResult
from app.shared.events.event_bus import EventBus


class FakeSynthesizeSpeech:
    def __init__(self, chunks=None):
        self._chunks = chunks or [b"audio1", b"audio2"]
        self.execute = AsyncMock(return_value=b"rest_audio")

    async def synthesize_stream(self, text):
        for chunk in self._chunks:
            yield chunk


async def fake_llm_stream(*tokens):
    for t in tokens:
        yield t


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def coordinator(event_bus):
    synth = FakeSynthesizeSpeech()
    validator = MagicMock()
    rc = ResponseCoordinator(event_bus, synth, validator)
    return rc, synth, validator


@pytest.mark.asyncio
async def test_stream_with_delimiter(coordinator):
    rc, synth, validator = coordinator
    validator.side_effect = lambda *a, **k: fake_llm_stream(
        "Hello ", "there! ", "###METADATA###", '{"should_advance": true, "reason": "Good answer"}'
    )

    result = await rc.stream_response(
        item={"type": "text", "text": "Q1", "expected_context": "ctx"},
        transcript="user said this",
        session_id="sess-1",
        turn_id="turn-1",
        question_id="q-1",
    )

    assert isinstance(result, StreamingResult)
    assert result.should_advance is True
    assert result.reason == "Good answer"
    assert result.token_count == 4  # 3 spoken tokens + 1 JSON token
    assert result.metadata["should_advance"] is True


@pytest.mark.asyncio
async def test_stream_without_delimiter(coordinator):
    rc, synth, validator = coordinator
    validator.side_effect = lambda *a, **k: fake_llm_stream("Just ", "some ", "text")

    result = await rc.stream_response(
        item={"type": "text", "text": "Q1", "expected_context": "ctx"},
        transcript="user said this",
        session_id="sess-1",
        turn_id="turn-1",
        question_id="q-1",
    )

    assert result.classification == "SYSTEM_ERROR"
    assert result.should_advance is False


@pytest.mark.asyncio
async def test_cancellation(coordinator):
    rc, synth, validator = coordinator

    async def slow_stream():
        yield "token1"
        await asyncio.sleep(0.5)
        yield "token2"

    validator.side_effect = lambda *a, **k: slow_stream()

    task = asyncio.create_task(rc.stream_response(
        item={"type": "text", "text": "Q1", "expected_context": "ctx"},
        transcript="user said this",
        session_id="sess-1",
        turn_id="turn-1",
        question_id="q-1",
    ))

    await asyncio.sleep(0.05)
    rc.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_tts_fallback_on_stream_error(coordinator):
    rc, synth, validator = coordinator

    async def bad_synth_stream(text):
        raise RuntimeError("TTS stream died")
        yield b""

    synth.synthesize_stream = bad_synth_stream

    validator.side_effect = lambda *a, **k: fake_llm_stream(
        "Hello! ", "###METADATA###", '{"should_advance": true}'
    )

    result = await rc.stream_response(
        item={"type": "text", "text": "Q1", "expected_context": "ctx"},
        transcript="user said this",
        session_id="sess-1",
        turn_id="turn-1",
        question_id="q-1",
    )

    assert result.should_advance is True
    synth.execute.assert_called_once()
