"""LLM provider management endpoints."""

import json
import logging
import urllib.request
import urllib.error
import asyncio
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.modules.provider.infrastructure.persistence.llm_provider_repository import LLMProviderRepository
from app.shared.security.envelope_encryption import encrypt_and_store, load_and_decrypt
from app.shared.constants.provider_urls import (
    OPENAI_API_URL, ANTHROPIC_API_URL, MISTRAL_API_URL, MOONSHOT_API_URL,
    OPENROUTER_API_URL, OLLAMA_API_URL, GOOGLE_API_URL,
)

router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])
_repo = LLMProviderRepository()
logger = logging.getLogger("llm_provider_routes")


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


class LLMModelFetchRequest(BaseModel):
    provider_id: Optional[str] = None
    provider_type: Optional[str] = "openai_compatible"
    base_url: Optional[str] = ""
    api_key: Optional[str] = ""


FALLBACK_MODELS = {
    "openai": [
        {"id": "gpt-4o", "name": "gpt-4o"},
        {"id": "gpt-4o-mini", "name": "gpt-4o-mini"},
        {"id": "o1", "name": "o1"},
        {"id": "o1-mini", "name": "o1-mini"},
        {"id": "gpt-4-turbo", "name": "gpt-4-turbo"},
    ],
    "anthropic": [
        {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet"},
        {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku"},
        {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus"},
    ],
    "google": [
        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
        {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
        {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
    ],
    "mistral": [
        {"id": "mistral-large-latest", "name": "Mistral Large"},
        {"id": "mistral-small-latest", "name": "Mistral Small"},
    ],
    "moonshot": [
        {"id": "moonshot-v1-8k", "name": "Moonshot v1 8k"},
        {"id": "moonshot-v1-32k", "name": "Moonshot v1 32k"},
    ],
    "ollama": [
        {"id": "llama3.2", "name": "Llama 3.2"},
        {"id": "mistral", "name": "Mistral"},
        {"id": "qwen2.5", "name": "Qwen 2.5"},
    ],
    "openai_compatible": [
        {"id": "gpt-4o-mini", "name": "gpt-4o-mini"},
        {"id": "gpt-4o", "name": "gpt-4o"},
        {"id": "claude-3-5-sonnet", "name": "claude-3-5-sonnet"},
        {"id": "deepseek-chat", "name": "deepseek-chat"},
    ],
}


def _fetch_models_sync(base_url: str, api_key: str, provider_type: str) -> List[Dict[str, str]]:
    url = (base_url or "").lstrip("=").strip().rstrip("/")
    if not url:
        if provider_type == "openai":
            url = OPENAI_API_URL
        elif provider_type == "anthropic":
            url = ANTHROPIC_API_URL
        elif provider_type == "mistral":
            url = MISTRAL_API_URL
        elif provider_type == "moonshot":
            url = MOONSHOT_API_URL
        elif provider_type == "openrouter":
            url = OPENROUTER_API_URL
        elif provider_type == "ollama":
            url = OLLAMA_API_URL

    if url and not url.startswith("http://") and not url.startswith("https://"):
        if "localhost" in url or "127.0.0.1" in url:
            url = f"http://{url}"
        else:
            url = f"https://{url}"

    if provider_type == "anthropic":
        endpoint = f"{ANTHROPIC_API_URL}/models"
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Accept": "application/json",
        }
    elif provider_type == "google":
        endpoint = f"{GOOGLE_API_URL}/models?key={api_key}"
        headers = {"Accept": "application/json"}
    else:
        # Standard OpenAI / OpenAI-compatible / Groq / OpenRouter / Ollama
        if not url.endswith("/models"):
            if not url.endswith("/v1"):
                endpoint = f"{url}/v1/models"
            else:
                endpoint = f"{url}/models"
        else:
            endpoint = url

        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

    try:
        req = urllib.request.Request(endpoint, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = []
            if isinstance(data, dict):
                raw_list = data.get("data") or data.get("models") or []
            elif isinstance(data, list):
                raw_list = data
            else:
                raw_list = []

            for item in raw_list:
                if isinstance(item, dict):
                    mid = item.get("id") or item.get("name") or ""
                    if mid.startswith("models/"):
                        mid = mid.replace("models/", "")
                    if mid:
                        models.append({"id": mid, "name": item.get("display_name") or mid})
                elif isinstance(item, str):
                    models.append({"id": item, "name": item})

            return models
    except Exception as e:
        logger.warning(f"[LLM_MODELS] Failed to fetch models from {endpoint}: {e}")
        return []


@router.get("")
async def list_llm_providers():
    providers = await _repo.list_all()
    for p in providers:
        p["credentials_enc"] = {"encrypted": True}
    return providers


@router.post("/fetch-models")
async def fetch_llm_models(req: LLMModelFetchRequest):
    base_url = req.base_url or ""
    api_key = req.api_key or ""
    provider_type = req.provider_type or "openai_compatible"

    if req.provider_id:
        p = await _repo.get_by_id(req.provider_id)
        if p and p.get("credentials_enc") and p.get("key_version"):
            creds = await load_and_decrypt(p["credentials_enc"], p["key_version"])
            if not api_key:
                api_key = creds.get("api_key", "")
            if not base_url:
                base_url = p.get("base_url", "")
            if not req.provider_type:
                provider_type = p.get("provider_type", "openai_compatible")

    models = await asyncio.to_thread(_fetch_models_sync, base_url, api_key, provider_type)

    if not models:
        fallback = FALLBACK_MODELS.get(provider_type, FALLBACK_MODELS["openai_compatible"])
        return {"models": fallback, "fetched": False}

    return {"models": models, "fetched": True}


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
    # Check if any deployed bot references this provider
    from app.modules.bot.infrastructure.persistence.bot_repository import BotRepository
    bot_repo = BotRepository()
    bots = await bot_repo.list_all()
    using_bots = [b["name"] for b in bots if b.get("is_deployed") and b.get("llm_provider_id") == provider_id]
    if using_bots:
        raise HTTPException(status_code=409, detail=f"Cannot delete — used by deployed bot(s): {', '.join(using_bots)}. Undeploy them first.")
    await _repo.delete(provider_id)
    return {"status": "deleted"}
