"""Bot management endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.modules.bot.infrastructure.persistence.postgres_bot_repository import PostgresBotRepository

router = APIRouter(prefix="/bots", tags=["bots"])
_repo = PostgresBotRepository()


class BotCreateRequest(BaseModel):
    name: str
    description: str = ""
    personality: str = ""
    system_prompt: str = ""
    llm_provider_id: Optional[str] = None
    llm_model: str = ""
    speech_provider_id: Optional[str] = None


class BotUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    system_prompt: Optional[str] = None
    llm_provider_id: Optional[str] = None
    llm_model: Optional[str] = None
    speech_provider_id: Optional[str] = None


@router.get("")
async def list_bots():
    return await _repo.list_all()


@router.post("")
async def create_bot(req: BotCreateRequest):
    bot_id = await _repo.create(req.model_dump())
    await _repo.activate(bot_id)
    return {"id": bot_id, "status": "created"}


@router.get("/active")
async def get_active_bot():
    bot = await _repo.get_active()
    if not bot:
        return {"active": None}
    return bot


@router.get("/{bot_id}")
async def get_bot(bot_id: str):
    bot = await _repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot


@router.put("/{bot_id}")
async def update_bot(bot_id: str, req: BotUpdateRequest):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    await _repo.update(bot_id, updates)
    await _repo.activate(bot_id)
    return {"status": "updated"}


@router.delete("/{bot_id}")
async def delete_bot(bot_id: str):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    await _repo.delete(bot_id)
    return {"status": "deleted"}


@router.post("/{bot_id}/activate")
async def activate_bot(bot_id: str):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    await _repo.activate(bot_id)
    return {"status": "activated", "bot_id": bot_id}
