import pytest
from app.shared.events.event_bus import EventBus, Event


@pytest.mark.asyncio
async def test_publish_to_sync_handler():
    bus = EventBus()
    received = []
    bus.subscribe("test_event", lambda e: received.append(e.payload))
    await bus.publish(Event(name="test_event", payload="hello", session_id="s1"))
    assert received == ["hello"]


@pytest.mark.asyncio
async def test_publish_to_async_handler():
    bus = EventBus()
    received = []

    async def handler(event):
        received.append(event.payload)

    bus.subscribe_async("test_event", handler)
    await bus.publish(Event(name="test_event", payload=42, session_id="s1"))
    assert received == [42]


@pytest.mark.asyncio
async def test_multiple_handlers():
    bus = EventBus()
    a, b = [], []
    bus.subscribe("e", lambda e: a.append(e.payload))
    bus.subscribe("e", lambda e: b.append(e.payload))
    await bus.publish_raw("e", "val", "s1")
    assert a == ["val"]
    assert b == ["val"]


@pytest.mark.asyncio
async def test_handler_error_does_not_propagate():
    bus = EventBus()

    def bad_handler(event):
        raise RuntimeError("boom")

    bus.subscribe("e", bad_handler)
    # Should NOT raise
    await bus.publish(Event(name="e", payload="x"))
