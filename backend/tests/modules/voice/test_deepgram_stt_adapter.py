import asyncio
import pytest
from app.modules.voice.infrastructure.external.deepgram_stt_adapter import DeepgramSTTAdapter


@pytest.mark.asyncio
async def test_deepgram_stt_adapter_queue_and_drain():
    adapter = DeepgramSTTAdapter()
    
    # Simulate items placed into internal queue (epoch-wrapped format)
    await adapter._queue.put({"epoch": 0, "data": {"channel": {"alternatives": [{"transcript": "partial"}]}, "is_final": False}})
    await adapter._queue.put({"epoch": 0, "data": {"channel": {"alternatives": [{"transcript": "final speech"}]}, "is_final": True}})

    # Test receive_any non-blocking — returns unwrapped data with _epoch key
    msg1 = await adapter.receive_any()
    assert msg1.get("channel", {}).get("alternatives", [{}])[0].get("transcript") == "partial"
    assert msg1.get("_epoch") == 0

    # Test drain_pending clears remaining items
    await adapter.drain_pending()
    msg2 = await adapter.receive_any()
    assert msg2 == {}

    await adapter.close()


@pytest.mark.asyncio
async def test_deepgram_stt_adapter_epoch_advance():
    adapter = DeepgramSTTAdapter()

    # Put items from epoch 0
    await adapter._queue.put({"epoch": 0, "data": {"channel": {"alternatives": [{"transcript": "stale"}]}, "is_final": True}})
    
    # Advance epoch to 1
    new_epoch = adapter.advance_epoch()
    assert new_epoch == 1

    # Put items from epoch 1
    await adapter._queue.put({"epoch": 1, "data": {"channel": {"alternatives": [{"transcript": "fresh"}]}, "is_final": True}})

    # drain_before(1) should discard epoch 0 items, keep epoch 1
    discarded = await adapter.drain_before(1)
    assert discarded == 1

    msg = await adapter.receive_any()
    assert msg.get("channel", {}).get("alternatives", [{}])[0].get("transcript") == "fresh"
    assert msg.get("_epoch") == 1

    await adapter.close()


@pytest.mark.asyncio
async def test_deepgram_stt_adapter_queue_overflow():
    adapter = DeepgramSTTAdapter()

    # Fill queue to maxsize (500)
    for i in range(500):
        await adapter._queue.put({"epoch": 0, "data": {"i": i}})
    
    assert adapter._queue.full()

    # Simulate what _listen_loop does when queue is full: discard oldest, put new
    if adapter._queue.full():
        try:
            adapter._queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    await adapter._queue.put({"epoch": 0, "data": {"i": 500}})

    # Queue should still be at maxsize
    assert adapter._queue.qsize() == 500

    await adapter.close()
