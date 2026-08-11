"""Bot management endpoints."""

import re
import json
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.modules.bot.infrastructure.persistence.postgres_bot_repository import PostgresBotRepository
from app.shared.schemas import BotResponse, BotActiveResponse, StatusResponse, BotDeployResponse

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


@router.get("", response_model=List[BotResponse])
async def list_bots():
    return await _repo.list_all()


@router.post("", response_model=StatusResponse)
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


@router.get("/speech-voices/{provider_id}")
async def list_speech_voices(provider_id: str):
    """Fetch actual voice names from a speech provider's API (e.g. Fish Audio voice library, ElevenLabs voices)."""
    from app.modules.provider.infrastructure.persistence.postgres_speech_provider_repository import PostgresSpeechProviderRepository
    from app.shared.security.envelope_encryption import load_and_decrypt
    from app.entrypoints.http.admin.speech_provider_routes import _fetch_fish_models_sync, _fetch_elevenlabs_data_sync

    speech_repo = PostgresSpeechProviderRepository()
    provider = await speech_repo.get_by_id(provider_id)
    if not provider:
        return {"voices": []}

    provider_type = provider.get("provider_type", "")

    try:
        creds = await load_and_decrypt(provider["credentials_enc"], provider.get("key_version", 1))
        api_key = creds.get("api_key", "")
        if not api_key:
            return {"voices": []}

        if provider_type == "fishaudio":
            _, voices, _ = await asyncio.to_thread(_fetch_fish_models_sync, api_key)
            return {"voices": voices}
        elif provider_type == "elevenlabs":
            _, voices, _ = await asyncio.to_thread(_fetch_elevenlabs_data_sync, api_key)
            # ElevenLabs voices don't have language info; tag them as 'multi'
            for v in voices:
                v["language"] = "en"
            return {"voices": voices}
        else:
            return {"voices": []}
    except Exception:
        return {"voices": []}


@router.get("/{bot_id}", response_model=BotResponse)
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
    """Return STT/TTS models grouped by language for the given provider."""
    from app.shared.constants.model_catalogs import get_speech_models
    return get_speech_models(provider_type)
