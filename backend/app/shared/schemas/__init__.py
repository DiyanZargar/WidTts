"""API Response schemas for frontend-consumed endpoints.

These describe the CURRENT response contracts — they do not change behavior.
"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class BotResponse(BaseModel):
    """Response for a single bot (GET /admin/api/bots/{id}, GET /admin/api/bots/active)."""
    id: str
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
    greeting: str = ""
    tts_custom_model: str = ""
    tts_custom_voice_id: str = ""
    tts_custom_endpoint: str = ""
    is_active: bool = False
    deploy_slug: Optional[str] = None
    is_deployed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BotActiveResponse(BaseModel):
    """Response for GET /admin/api/bots/active when no bot is active."""
    active: Optional[BotResponse] = None


class TokenResponse(BaseModel):
    """Response for POST /api/bot/{slug}/token and POST /realtime/token."""
    token: str
    room_name: str
    server_url: str
    session_id: str
    bot_name: str = "Assistant"


class PublicBotResponse(BaseModel):
    """Response for GET /api/bot/{slug} — public bot info."""
    id: str
    name: str = ""
    description: str = ""
    is_deployed: bool = False


class StatusResponse(BaseModel):
    """Generic status response for CRUD operations."""
    status: str
    id: Optional[str] = None
    bot_id: Optional[str] = None
    slug: Optional[str] = None
    url: Optional[str] = None


class BotDeployResponse(BaseModel):
    """Response for POST /admin/api/bots/{id}/deploy."""
    status: str
    bot_id: str
    slug: str
    url: str
