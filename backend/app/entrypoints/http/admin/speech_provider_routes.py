"""Speech provider management endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.modules.provider.infrastructure.persistence.postgres_speech_provider_repository import PostgresSpeechProviderRepository
from app.shared.security.envelope_encryption import encrypt_and_store

router = APIRouter(prefix="/speech-providers", tags=["speech-providers"])
_repo = PostgresSpeechProviderRepository()


class SpeechProviderCreateRequest(BaseModel):
    name: str
    provider_type: str  # 'deepgram' | 'elevenlabs'
    credentials: Dict[str, Any]  # plaintext {"api_key": "..."}
    stt_model: str = ""
    stt_language: str = "en"
    stt_extra: Dict[str, Any] = {}
    tts_model: str = ""
    tts_voice_id: str = ""
    tts_extra: Dict[str, Any] = {}


class SpeechProviderUpdateRequest(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    stt_model: Optional[str] = None
    stt_language: Optional[str] = None
    stt_extra: Optional[Dict[str, Any]] = None
    tts_model: Optional[str] = None
    tts_voice_id: Optional[str] = None
    tts_extra: Optional[Dict[str, Any]] = None


@router.get("")
async def list_speech_providers():
    providers = await _repo.list_all()
    for p in providers:
        p["credentials_enc"] = {"encrypted": True}
    return providers


@router.post("")
async def create_speech_provider(req: SpeechProviderCreateRequest):
    blob, key_version = await encrypt_and_store(req.credentials)
    provider_data = {
        "name": req.name,
        "provider_type": req.provider_type,
        "credentials_enc": blob,
        "key_version": key_version,
        "stt_model": req.stt_model,
        "stt_language": req.stt_language,
        "stt_extra": req.stt_extra,
        "tts_model": req.tts_model,
        "tts_voice_id": req.tts_voice_id,
        "tts_extra": req.tts_extra,
    }
    pid = await _repo.create(provider_data)
    return {"id": pid, "status": "created"}


@router.get("/{provider_id}")
async def get_speech_provider(provider_id: str):
    provider = await _repo.get_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Speech provider not found")
    provider["credentials_enc"] = {"encrypted": True}
    return provider


@router.put("/{provider_id}")
async def update_speech_provider(provider_id: str, req: SpeechProviderUpdateRequest):
    existing = await _repo.get_by_id(provider_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Speech provider not found")

    updates = {}
    for k, v in req.model_dump().items():
        if v is not None and k != "credentials":
            updates[k] = v

    if req.credentials:
        blob, key_version = await encrypt_and_store(req.credentials)
        updates["credentials_enc"] = blob
        updates["key_version"] = key_version

    await _repo.update(provider_id, updates)
    return {"status": "updated"}


@router.delete("/{provider_id}")
async def delete_speech_provider(provider_id: str):
    existing = await _repo.get_by_id(provider_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Speech provider not found")
    await _repo.delete(provider_id)
    return {"status": "deleted"}
