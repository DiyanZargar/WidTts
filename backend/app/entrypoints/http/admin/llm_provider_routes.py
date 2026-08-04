"""LLM provider management endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.modules.provider.infrastructure.persistence.postgres_llm_provider_repository import PostgresLLMProviderRepository
from app.shared.security.envelope_encryption import encrypt_and_store
from app.shared.security.credential_masking import mask_dict

router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])
_repo = PostgresLLMProviderRepository()


class LLMProviderCreateRequest(BaseModel):
    name: str
    provider_type: str  # 'openai' | 'anthropic' | 'google' | 'openai_compatible'
    base_url: str = ""
    credentials: Dict[str, Any]  # plaintext {"api_key": "..."}
    is_default: bool = False


class LLMProviderUpdateRequest(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    base_url: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


@router.get("")
async def list_llm_providers():
    providers = await _repo.list_all()
    # Mask credentials in response
    for p in providers:
        p["credentials_enc"] = {"encrypted": True}
    return providers


@router.post("")
async def create_llm_provider(req: LLMProviderCreateRequest):
    blob, key_version = await encrypt_and_store(req.credentials)
    provider_data = {
        "name": req.name,
        "provider_type": req.provider_type,
        "base_url": req.base_url,
        "credentials_enc": blob,
        "key_version": key_version,
        "is_default": req.is_default,
    }
    pid = await _repo.create(provider_data)
    return {"id": pid, "status": "created"}


@router.get("/{provider_id}")
async def get_llm_provider(provider_id: str):
    provider = await _repo.get_by_id(provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    provider["credentials_enc"] = {"encrypted": True}
    return provider


@router.put("/{provider_id}")
async def update_llm_provider(provider_id: str, req: LLMProviderUpdateRequest):
    existing = await _repo.get_by_id(provider_id)
    if not existing:
        raise HTTPException(status_code=404, detail="LLM provider not found")

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
async def delete_llm_provider(provider_id: str):
    existing = await _repo.get_by_id(provider_id)
    if not existing:
        raise HTTPException(status_code=404, detail="LLM provider not found")
    await _repo.delete(provider_id)
    return {"status": "deleted"}
