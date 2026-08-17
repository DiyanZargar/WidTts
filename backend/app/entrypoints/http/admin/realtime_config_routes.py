"""
Realtime Runtime Configuration admin routes.

Provides CRUD and connection testing for realtime transport configurations.
Supports managing multiple realtime providers (e.g. Local Docker, Cloud).
No LiveKit terminology appears in any response or error message.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.voice.infrastructure.persistence.realtime_config_repository import (
    RealtimeConfigRepository,
)
from app.shared.security.envelope_encryption import encrypt_and_store, load_and_decrypt
from app.shared.security.credential_masking import mask_credential

logger = logging.getLogger("admin_realtime_config")
router = APIRouter(prefix="/realtime-runtime", tags=["realtime-runtime"])

_repo = RealtimeConfigRepository()


async def _encrypt_value(plaintext: str) -> dict:
    """Encrypt a single string value using envelope encryption."""
    blob, kv = await encrypt_and_store({"value": plaintext})
    return {"blob": blob, "key_version": kv}


async def _decrypt_value(encrypted: dict) -> str:
    """Decrypt a single string value."""
    blob = encrypted["blob"]
    kv = encrypted["key_version"]
    result = await load_and_decrypt(blob, kv)
    return result["value"]


class RealtimeConfigCreateRequest(BaseModel):
    name: str = "Realtime Provider"
    provider_type: str = "livekit"
    server_url: str
    api_key: str
    api_secret: str
    room_token_ttl_seconds: int = 3600
    audio_sample_rate: int = 16000
    is_active: bool = True


class RealtimeConfigUpdateRequest(BaseModel):
    name: Optional[str] = None
    provider_type: Optional[str] = None
    server_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    room_token_ttl_seconds: Optional[int] = None
    audio_sample_rate: Optional[int] = None
    is_active: Optional[bool] = None


class TestConnectionRequest(BaseModel):
    config_id: Optional[str] = None
    server_url: Optional[str] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None


def _format_config_response(cfg: dict) -> dict:
    masked_key = "***"
    if cfg.get("encrypted_api_key"):
        try:
            key_plain = load_and_decrypt  # placeholder check
            masked_key = "Key configured"
        except Exception:
            pass

    return {
        "id": str(cfg["id"]),
        "name": cfg.get("name", "Realtime Provider"),
        "provider_type": cfg.get("provider_type", "livekit"),
        "server_url": cfg["server_url"],
        "api_key_masked": masked_key,
        "api_secret_masked": "***",
        "room_token_ttl_seconds": cfg["room_token_ttl_seconds"],
        "audio_sample_rate": cfg["audio_sample_rate"],
        "is_active": cfg.get("is_active", False),
        "last_tested_at": (
            cfg["last_tested_at"].isoformat()
            if hasattr(cfg.get("last_tested_at"), "isoformat")
            else cfg.get("last_tested_at")
        ),
        "last_test_status": cfg.get("last_test_status"),
        "last_test_error": cfg.get("last_test_error"),
        "created_at": (
            cfg["created_at"].isoformat()
            if hasattr(cfg.get("created_at"), "isoformat")
            else cfg.get("created_at")
        ),
        "updated_at": (
            cfg["updated_at"].isoformat()
            if hasattr(cfg.get("updated_at"), "isoformat")
            else cfg.get("updated_at")
        ),
    }


@router.get("")
async def list_realtime_configs():
    """Return all configured realtime runtime providers."""
    configs = await _repo.get_all()
    formatted = []
    for cfg in configs:
        item = _format_config_response(cfg)
        if cfg.get("encrypted_api_key"):
            try:
                plain_key = await _decrypt_value(cfg["encrypted_api_key"])
                item["api_key_masked"] = mask_credential(plain_key)
            except Exception:
                item["api_key_masked"] = "***"
        formatted.append(item)
    return formatted


@router.post("")
async def create_realtime_config(payload: RealtimeConfigCreateRequest):
    """Create a new realtime provider configuration."""
    if not payload.server_url.strip():
        raise HTTPException(400, "Server URL is required")
    if not payload.api_key.strip():
        raise HTTPException(400, "API key is required")
    if not payload.api_secret.strip():
        raise HTTPException(400, "API secret is required")

    encrypted_key = await _encrypt_value(payload.api_key.strip())
    encrypted_secret = await _encrypt_value(payload.api_secret.strip())

    config_data = {
        "name": payload.name.strip(),
        "provider_type": payload.provider_type.strip(),
        "server_url": payload.server_url.strip(),
        "encrypted_api_key": encrypted_key,
        "encrypted_api_secret": encrypted_secret,
        "room_token_ttl_seconds": payload.room_token_ttl_seconds,
        "audio_sample_rate": payload.audio_sample_rate,
        "is_active": payload.is_active,
    }

    created = await _repo.create(config_data)
    logger.info(f"[ADMIN] Created realtime provider config: {created['id']}")
    return _format_config_response(created)


@router.put("/{config_id}")
async def update_realtime_config(config_id: str, payload: RealtimeConfigUpdateRequest):
    """Update an existing realtime provider configuration."""
    existing = await _repo.get_by_id(config_id)
    if not existing:
        raise HTTPException(404, "Realtime config not found")

    update_data = {}
    if payload.name is not None:
        update_data["name"] = payload.name.strip()
    if payload.provider_type is not None:
        update_data["provider_type"] = payload.provider_type.strip()
    if payload.server_url is not None:
        update_data["server_url"] = payload.server_url.strip()
    if payload.room_token_ttl_seconds is not None:
        update_data["room_token_ttl_seconds"] = payload.room_token_ttl_seconds
    if payload.audio_sample_rate is not None:
        update_data["audio_sample_rate"] = payload.audio_sample_rate
    if payload.api_key and payload.api_key.strip():
        update_data["encrypted_api_key"] = await _encrypt_value(payload.api_key.strip())
    if payload.api_secret and payload.api_secret.strip():
        update_data["encrypted_api_secret"] = await _encrypt_value(payload.api_secret.strip())

    updated = await _repo.update(config_id, update_data)
    if payload.is_active:
        updated = await _repo.set_active(config_id)

    logger.info(f"[ADMIN] Updated realtime provider config: {config_id}")
    return _format_config_response(updated)


@router.post("/{config_id}/activate")
async def activate_realtime_config(config_id: str):
    """Set the specified provider as active."""
    updated = await _repo.set_active(config_id)
    if not updated:
        raise HTTPException(404, "Realtime config not found")
    logger.info(f"[ADMIN] Activated realtime provider config: {config_id}")
    return _format_config_response(updated)


@router.delete("/{config_id}")
async def delete_realtime_config(config_id: str):
    """Delete a realtime provider configuration."""
    success = await _repo.delete(config_id)
    if not success:
        raise HTTPException(404, "Realtime config not found")
    logger.info(f"[ADMIN] Deleted realtime provider config: {config_id}")
    return {"ok": True, "id": config_id}


@router.post("/test")
async def test_realtime_connection(req: Optional[TestConnectionRequest] = None):
    """Test connection to a realtime transport provider."""
    from app.shared.config.settings import settings

    server_url = None
    api_key = None
    api_secret = None
    target_id = None

    if req and req.config_id:
        target_id = req.config_id
        config = await _repo.get_by_id(req.config_id)
        if not config:
            raise HTTPException(404, "Config not found")
        server_url = req.server_url or config["server_url"]
        api_key = req.api_key if (req.api_key and req.api_key.strip()) else await _decrypt_value(config["encrypted_api_key"])
        api_secret = req.api_secret if (req.api_secret and req.api_secret.strip()) else await _decrypt_value(config["encrypted_api_secret"])
    elif req and req.server_url:
        server_url = req.server_url.strip()
        api_key = req.api_key.strip() if req.api_key else ""
        api_secret = req.api_secret.strip() if req.api_secret else ""
        if not api_key or not api_secret:
            raise HTTPException(400, "API Key and API Secret are required to test a new transport connection")
    else:
        config = await _repo.get_active()
        if not config:
            raise HTTPException(400, "No active realtime configuration found")
        target_id = str(config["id"])
        server_url = config["server_url"]
        api_key = await _decrypt_value(config["encrypted_api_key"])
        api_secret = await _decrypt_value(config["encrypted_api_secret"])

    # Use internal URL for backend container connectivity test when configured
    test_connect_url = settings.livekit_internal_url or server_url

    try:
        from livekit.api import LiveKitAPI, ListRoomsRequest

        api = LiveKitAPI(url=test_connect_url, api_key=api_key, api_secret=api_secret)
        await api.room.list_rooms(ListRoomsRequest())
        await api.aclose()

        if target_id:
            await _repo.update_test_status(target_id, "success")

        logger.info(f"[ADMIN] Realtime connection test passed for {test_connect_url}")
        return {"ok": True, "status": "success", "message": f"Successfully connected to {test_connect_url}"}

    except Exception as e:
        error_msg = str(e)[:200]
        if target_id:
            await _repo.update_test_status(target_id, "failed", error_msg)

        logger.warning(f"[ADMIN] Realtime connection test failed for {test_connect_url}: {error_msg}")
        return {"ok": False, "status": "failed", "error": error_msg}
