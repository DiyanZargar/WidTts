import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.modules.voice.infrastructure.external.deepgram_tts_adapter import DeepgramTTSAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeFlushed:
    type = "Flushed"
    sequence_id = 1


class FakeWarning:
    type = "Warning"
    message = "something odd"


class FakeMetadata:
    type = "Metadata"
    sample_rate = 48000


def _make_mocks():
    """Return a tuple of (mock_client_cls, mock_ctx, mock_conn) wired correctly.

    The SDK's .connect() is a sync method returning an async context manager.
    We mock the chain so connect() returns a MagicMock that supports
    __aenter__ / __aexit__.
    """
    mock_client = MagicMock()
    mock_ctx = MagicMock()
    mock_conn = AsyncMock()

    mock_client.speak.v1.connect = MagicMock(return_value=mock_ctx)
    mock_client.speak.v2.connect = MagicMock(return_value=mock_ctx)
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_client, mock_ctx, mock_conn


# ---------------------------------------------------------------------------
# connect_stream
# ---------------------------------------------------------------------------

@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.AsyncDeepgramClient")
@pytest.mark.asyncio
async def test_connect_stream_opens_websocket(mock_client_cls):
    mock_client, mock_ctx, mock_conn = _make_mocks()
    mock_client_cls.return_value = mock_client

    adapter = DeepgramTTSAdapter()
    await adapter.connect_stream()

    assert adapter._stream_connected is True
    assert adapter._conn is mock_conn
    assert adapter._listen_task is not None

    # Event handlers registered
    calls = mock_conn.on.call_args_list
    event_types = [c[0][0] for c in calls]
    assert "message" in event_types
    assert "open" in event_types
    assert "close" in event_types
    assert "error" in event_types

    # start_listening launched as background task
    mock_conn.start_listening.assert_called_once()

    await adapter.close()


@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.AsyncDeepgramClient")
@pytest.mark.asyncio
async def test_connect_stream_reconnects_when_listener_died(mock_client_cls):
    """If the background listener task finished, connect_stream should reconnect."""
    mock_client, mock_ctx, mock_conn = _make_mocks()
    mock_client_cls.return_value = mock_client

    adapter = DeepgramTTSAdapter()
    await adapter.connect_stream()

    # Simulate listener dying
    task = adapter._listen_task
    assert task is not None, "listen_task should exist after connect"
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    adapter._listen_task = None  # mirrors cleanup_connection behavior

    # Reconnect should spin up a new connection
    await adapter.connect_stream()
    assert adapter._stream_connected is True
    assert adapter._conn is mock_conn
    assert adapter._listen_task is not None
    assert not adapter._listen_task.done()

    await adapter.close()


# ---------------------------------------------------------------------------
# _on_message
# ---------------------------------------------------------------------------

def test_on_message_bytes_enqueued():
    adapter = DeepgramTTSAdapter()
    chunk = b"fake_audio_data"
    adapter._on_message(chunk)
    assert adapter._tts_queue.get_nowait() == chunk


def test_on_message_flushed_puts_sentinel():
    adapter = DeepgramTTSAdapter()
    adapter._on_message(FakeFlushed())
    assert adapter._tts_queue.get_nowait() is None


def test_on_message_warning_logged(caplog):
    import logging
    adapter = DeepgramTTSAdapter()
    with caplog.at_level(logging.WARNING):
        adapter._on_message(FakeWarning())
    assert "Warning" in caplog.text


def test_on_message_metadata_logged(caplog):
    import logging
    adapter = DeepgramTTSAdapter()
    with caplog.at_level(logging.INFO):
        adapter._on_message(FakeMetadata())
    assert "Metadata" in caplog.text


def test_on_message_bytes_drops_when_queue_full(caplog):
    import logging
    adapter = DeepgramTTSAdapter()
    adapter._tts_queue = asyncio.Queue(maxsize=1)
    adapter._tts_queue.put_nowait(b"occupant")
    with caplog.at_level(logging.WARNING):
        adapter._on_message(b"new_chunk")
    assert "dropping" in caplog.text.lower()


# ---------------------------------------------------------------------------
# synthesize_stream
# ---------------------------------------------------------------------------

@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.AsyncDeepgramClient")
@pytest.mark.asyncio
async def test_synthesize_stream_sends_text_and_yields_chunks(mock_client_cls):
    mock_client, mock_ctx, mock_conn = _make_mocks()
    mock_client_cls.return_value = mock_client

    adapter = DeepgramTTSAdapter()
    await adapter.connect_stream()

    # Prevent synthesize_stream from draining our pre-seeded chunks
    adapter._drain_queue = lambda: None

    # Pre-seed queue with chunks + sentinel
    adapter._tts_queue.put_nowait(b"chunk_1")
    adapter._tts_queue.put_nowait(b"chunk_2")
    adapter._tts_queue.put_nowait(None)

    chunks = []
    async for chunk in adapter.synthesize_stream("Hello world"):
        chunks.append(chunk)

    assert chunks == [b"chunk_1", b"chunk_2"]
    if adapter._is_v2:
        mock_conn.send_speak.assert_called_once()
    else:
        mock_conn.send_text.assert_called_once()
    mock_conn.send_flush.assert_called_once()

    await adapter.close()


@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.AsyncDeepgramClient")
@patch("asyncio.wait_for")
@pytest.mark.asyncio
async def test_synthesize_stream_timeout_raises(mock_wait_for, mock_client_cls):
    mock_client, mock_ctx, mock_conn = _make_mocks()
    mock_client_cls.return_value = mock_client

    adapter = DeepgramTTSAdapter()
    await adapter.connect_stream()

    # Force wait_for to timeout immediately
    mock_wait_for.side_effect = asyncio.TimeoutError

    with pytest.raises(RuntimeError, match="TTS streaming timeout"):
        async for _ in adapter.synthesize_stream("Hello world"):
            pass

    await adapter.close()


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------

@patch("app.modules.voice.infrastructure.external.deepgram_tts_adapter.AsyncDeepgramClient")
@pytest.mark.asyncio
async def test_close_cancels_listener_and_exits_context(mock_client_cls):
    mock_client, mock_ctx, mock_conn = _make_mocks()
    mock_client_cls.return_value = mock_client

    adapter = DeepgramTTSAdapter()
    await adapter.connect_stream()
    listen_task = adapter._listen_task

    await adapter.close()

    assert adapter._stream_connected is False
    assert adapter._conn is None
    assert adapter._ctx is None
    assert listen_task is None or listen_task.done()
    mock_conn.send_close.assert_called_once()
    mock_ctx.__aexit__.assert_called_once()


# ---------------------------------------------------------------------------
# REST fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_synthesize_uses_rest_fallback():
    adapter = DeepgramTTSAdapter()
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = AsyncMock()
        mock_resp.content = b"rest_audio"
        mock_post.return_value = mock_resp

        audio = await adapter.synthesize("Test text")
        assert audio == b"rest_audio"
