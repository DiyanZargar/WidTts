import pytest
from app.modules.conversation.application.services.task_router import TaskRouter


@pytest.mark.asyncio
async def test_route_to_registered_handler():
    router = TaskRouter()
    called_with = {}

    async def handler(ctx):
        called_with["ctx"] = ctx
        return {"handled": True}

    router.register("STOP", handler)
    result = await router.route("STOP", {"session_id": "s1"})

    assert result["handled"] is True
    assert called_with["ctx"]["session_id"] == "s1"


@pytest.mark.asyncio
async def test_fallback_for_unregistered():
    router = TaskRouter()
    result = await router.route("UNKNOWN", {"session_id": "s1"})
    assert result["handled"] is False


@pytest.mark.asyncio
async def test_custom_fallback():
    router = TaskRouter()

    async def fallback(ctx):
        return {"fallback": True}

    router.set_fallback(fallback)
    result = await router.route("UNKNOWN", {})
    assert result["fallback"] is True
