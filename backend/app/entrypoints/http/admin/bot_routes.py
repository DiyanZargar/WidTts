"""Bot management endpoints."""

import re
import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
from app.modules.bot.infrastructure.persistence.bot_repository import BotRepository
from app.shared.schemas import BotResponse, StatusResponse

router = APIRouter(prefix="/bots", tags=["bots"])
_repo = BotRepository()


def _generate_slug(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip())
    slug = slug.strip('-')
    return slug or "bot"


class BotCreateRequest(BaseModel):
    name: str
    description: str = ""
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
    greeting: str = ""


class BotUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
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
    greeting: Optional[str] = None


@router.get("", response_model=List[BotResponse])
async def list_bots():
    return await _repo.list_all()


import sqlite3


@router.post("", response_model=StatusResponse)
async def create_bot(req: BotCreateRequest):
    data = req.model_dump()
    for pid_field in ("llm_provider_id", "stt_provider_id", "tts_provider_id"):
        if data.get(pid_field) in ("", "string", "null"):
            data[pid_field] = None
    if isinstance(data.get("stt_languages"), list) and data["stt_languages"] == ["string"]:
        data["stt_languages"] = ["en"]
    if isinstance(data.get("tts_languages"), list) and data["tts_languages"] == ["string"]:
        data["tts_languages"] = ["en"]

    try:
        bot_id = await _repo.create(data)
        await _repo.update(bot_id, {"name_locked": True})
        await _repo.activate(bot_id)
        return {"id": bot_id, "status": "created"}
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Database constraint error: Check that llm_provider_id, stt_provider_id, and tts_provider_id are valid provider UUIDs. ({str(e)})"
        )


@router.get("/active", response_model=Optional[BotResponse])
async def get_active_bot():
    bot = await _repo.get_active()
    return bot


@router.get("/speech-models/{provider_type}")
async def list_speech_models(provider_type: str):
    return _get_speech_models(provider_type)


@router.get("/speech-voices/{provider_id}")
async def list_speech_voices(provider_id: str):
    """Fetch actual voice names from a speech provider's API (e.g. Fish Audio voice library, ElevenLabs voices, Deepgram Aura).
    
    Accepts either a provider UUID or provider_type ('elevenlabs', 'fishaudio', 'deepgram').
    """
    from app.modules.provider.infrastructure.persistence.speech_provider_repository import SpeechProviderRepository
    from app.shared.security.envelope_encryption import load_and_decrypt
    from app.entrypoints.http.admin.speech_provider_routes import _fetch_fish_models_sync, _fetch_elevenlabs_data_sync
    from app.shared.constants.model_catalogs import get_speech_models

    speech_repo = SpeechProviderRepository()
    provider = await speech_repo.get_by_id(provider_id)
    if not provider:
        all_providers = await speech_repo.list_all()
        matching = [p for p in all_providers if p.get("provider_type") == provider_id]
        if matching:
            provider = matching[0]

    provider_type = provider.get("provider_type", "") if provider else provider_id

    if provider_type == "deepgram":
        catalog = get_speech_models("deepgram")
        return {"voices": catalog.get("tts", [])}

    if not provider:
        catalog = get_speech_models(provider_type)
        return {"voices": catalog.get("tts", [])}

    try:
        creds = await load_and_decrypt(provider["credentials_enc"], provider.get("key_version", 1))
        api_key = creds.get("api_key", "")
        if not api_key:
            catalog = get_speech_models(provider_type)
            return {"voices": catalog.get("tts", [])}

        if provider_type == "fishaudio":
            _, voices, _ = await asyncio.to_thread(_fetch_fish_models_sync, api_key)
            return {"voices": voices}
        elif provider_type == "elevenlabs":
            _, voices, _ = await asyncio.to_thread(_fetch_elevenlabs_data_sync, api_key)
            for v in voices:
                v["language"] = "en"
            return {"voices": voices}
        else:
            catalog = get_speech_models(provider_type)
            return {"voices": catalog.get("tts", [])}
    except Exception:
        catalog = get_speech_models(provider_type)
        return {"voices": catalog.get("tts", [])}


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot(bot_id: str):
    bot = await _repo.get_by_id(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return bot


@router.put("/{bot_id}", response_model=BotResponse)
async def update_bot(bot_id: str, req: BotUpdateRequest):
    existing = await _repo.get_by_id(bot_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Bot not found")

    # Filter out None and Swagger dummy placeholders
    updates = {}
    for k, v in req.model_dump().items():
        if v is not None:
            if isinstance(v, str) and v == "string":
                continue
            if isinstance(v, list) and v == ["string"]:
                continue
            updates[k] = v

    # Convert empty provider IDs to None so SQLite doesn't fail foreign keys
    for pid_field in ("llm_provider_id", "stt_provider_id", "tts_provider_id"):
        if pid_field in updates and updates[pid_field] in ("", "null"):
            updates[pid_field] = None

    # Prevent name changes once locked
    if existing.get("name_locked") and "name" in updates:
        del updates["name"]

    try:
        await _repo.update(bot_id, updates)
        await _repo.activate(bot_id)
        updated_bot = await _repo.get_by_id(bot_id)
        return updated_bot
    except sqlite3.IntegrityError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Database constraint error: Check that llm_provider_id, stt_provider_id, and tts_provider_id are valid provider UUIDs. ({str(e)})"
        )


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
        if not await _repo.slug_exists(slug, exclude_bot_id=bot_id):
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
