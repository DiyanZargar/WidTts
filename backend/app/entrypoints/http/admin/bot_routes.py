"""Bot management endpoints."""

import re
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.modules.bot.infrastructure.persistence.postgres_bot_repository import PostgresBotRepository

router = APIRouter(prefix="/bots", tags=["bots"])
_repo = PostgresBotRepository()


def _generate_slug(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip())
    slug = slug.strip('-')
    return slug or "bot"


class BotCreateRequest(BaseModel):
    name: str
    description: str = ""
    personality: str = ""
    system_prompt: str = ""
    llm_provider_id: Optional[str] = None
    llm_model: str = ""
    stt_provider_id: Optional[str] = None
    tts_provider_id: Optional[str] = None
    stt_model: str = ""
    tts_model: str = ""
    stt_languages: List[str] = ["en"]
    stt_primary_language: str = "en"
    tts_languages: List[str] = ["en"]
    tts_primary_language: str = "en"


class BotUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    system_prompt: Optional[str] = None
    llm_provider_id: Optional[str] = None
    llm_model: Optional[str] = None
    stt_provider_id: Optional[str] = None
    tts_provider_id: Optional[str] = None
    stt_model: Optional[str] = None
    tts_model: Optional[str] = None
    stt_languages: Optional[List[str]] = None
    stt_primary_language: Optional[str] = None
    tts_languages: Optional[List[str]] = None
    tts_primary_language: Optional[str] = None


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


@router.get("/speech-models/{provider_type}")
async def list_speech_models(provider_type: str):
    return _get_speech_models(provider_type)


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
    if existing.get("is_deployed"):
        raise HTTPException(status_code=409, detail=f"Cannot delete \"{existing.get('name', 'bot')}\" — it is currently deployed. Undeploy it first.")
    await _repo.delete(bot_id)
    return {"status": "deleted"}


@router.post("/{bot_id}/activate")
async def activate_bot(bot_id: str):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    await _repo.activate(bot_id)
    return {"status": "activated", "bot_id": bot_id}


@router.post("/{bot_id}/deploy")
async def deploy_bot(bot_id: str):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    if existing.get("is_deployed") and existing.get("deploy_slug"):
        return {"status": "deployed", "bot_id": bot_id, "slug": existing["deploy_slug"], "url": f"/bot/{existing['deploy_slug']}"}
    base_slug = _generate_slug(existing.get("name", "bot"))
    slug = base_slug
    suffix = 1
    while True:
        if not await _repo.get_by_slug(slug):
            break
        suffix += 1
        slug = f"{base_slug}-{suffix}"
    await _repo.deploy(bot_id, slug)
    return {"status": "deployed", "bot_id": bot_id, "slug": slug, "url": f"/bot/{slug}"}


@router.post("/{bot_id}/undeploy")
async def undeploy_bot(bot_id: str):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")
    await _repo.undeploy(bot_id)
    return {"status": "undeployed", "bot_id": bot_id}


def _get_speech_models(provider_type: str) -> dict:
    if provider_type == "deepgram":
        return {
            "stt": [
                {"id": "nova-3", "name": "Nova 3 (Latest)"},
                {"id": "nova-2", "name": "Nova 2"},
                {"id": "nova", "name": "Nova"},
                {"id": "nova-2-meeting", "name": "Nova 2 Meeting"},
                {"id": "nova-2-phonecall", "name": "Nova 2 Phonecall"},
                {"id": "nova-2-video", "name": "Nova 2 Video"},
                {"id": "nova-2-medical", "name": "Nova 2 Medical"},
                {"id": "nova-2-finance", "name": "Nova 2 Finance"},
                {"id": "base", "name": "Base"},
                {"id": "base-meeting", "name": "Base Meeting"},
                {"id": "base-phonecall", "name": "Base Phonecall"},
                {"id": "enhanced", "name": "Enhanced"},
                {"id": "enhanced-meeting", "name": "Enhanced Meeting"},
                {"id": "enhanced-phonecall", "name": "Enhanced Phonecall"},
            ],
            "tts": [
                {"id": "flux-aura-en", "name": "Flux Aura (Female, English)"},
                {"id": "flux-rufus-en", "name": "Flux Rufus (Male, English)"},
                {"id": "aura-asteria-en", "name": "Aura Asteria (Female, English)"},
                {"id": "aura-orion-en", "name": "Aura Orion (Male, English)"},
                {"id": "aura-luna-en", "name": "Aura Luna (Female, English)"},
                {"id": "aura-arcas-en", "name": "Aura Arcas (Male, English)"},
                {"id": "aura-2-athena-en", "name": "Aura 2 Athena (Female, English)"},
                {"id": "aura-2-hera-en", "name": "Aura 2 Hera (Female, English)"},
                {"id": "aura-2-zeus-en", "name": "Aura 2 Zeus (Male, English)"},
                {"id": "aura-2-perseus-en", "name": "Aura 2 Perseus (Male, English)"},
                {"id": "aura-2-stella-en", "name": "Aura 2 Stella (Female, English)"},
                {"id": "aura-2-angulus-en", "name": "Aura 2 Angulus (Male, English)"},
            ],
            "languages": [
                {"code": "en", "name": "English"},
                {"code": "en-US", "name": "English (US)"},
                {"code": "en-GB", "name": "English (UK)"},
                {"code": "ar", "name": "Arabic"},
                {"code": "es", "name": "Spanish"},
                {"code": "fr", "name": "French"},
                {"code": "de", "name": "German"},
                {"code": "hi", "name": "Hindi"},
                {"code": "ja", "name": "Japanese"},
                {"code": "ko", "name": "Korean"},
                {"code": "pt", "name": "Portuguese"},
                {"code": "zh", "name": "Chinese"},
            ],
        }
    elif provider_type == "elevenlabs":
        return {
            "stt": [{"id": "scribe_v1", "name": "Scribe v1"}],
            "tts": [
                {"id": "eleven_multilingual_v2", "name": "Multilingual v2"},
                {"id": "eleven_turbo_v2", "name": "Turbo v2"},
                {"id": "eleven_monolingual_v1", "name": "Monolingual v1"},
            ],
            "languages": [
                {"code": "en", "name": "English"},
                {"code": "ar", "name": "Arabic"},
                {"code": "es", "name": "Spanish"},
                {"code": "fr", "name": "French"},
                {"code": "de", "name": "German"},
                {"code": "hi", "name": "Hindi"},
                {"code": "ja", "name": "Japanese"},
                {"code": "ko", "name": "Korean"},
                {"code": "pt", "name": "Portuguese"},
                {"code": "zh", "name": "Chinese"},
                {"code": "nl", "name": "Dutch"},
                {"code": "tr", "name": "Turkish"},
                {"code": "pl", "name": "Polish"},
                {"code": "sv", "name": "Swedish"},
                {"code": "it", "name": "Italian"},
            ],
        }
    return {"stt": [], "tts": [], "languages": []}
