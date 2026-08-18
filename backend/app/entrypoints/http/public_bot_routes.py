"""
Public bot routes — accessed by end users via deploy links.

These endpoints are unauthenticated. They allow users to:
1. Fetch a deployed bot's public info by slug
2. Mint a LiveKit token for a specific deployed bot
"""

import uuid
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.bot.infrastructure.persistence.bot_repository import (
    BotRepository,
)
from app.modules.voice.infrastructure.persistence.realtime_config_repository import (
    RealtimeConfigRepository,
)
from app.shared.schemas import TokenResponse, PublicBotResponse

logger = logging.getLogger("public_bot_routes")
router = APIRouter(prefix="/api/bot", tags=["public-bot"])

_bot_repo = BotRepository()
_config_repo = RealtimeConfigRepository()


@router.get("/{slug}", response_model=PublicBotResponse)
async def get_bot_by_slug(slug: str):
    """Get a deployed bot's public info by slug."""
    bot = await _bot_repo.get_by_slug(slug)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {
        "id": bot["id"],
        "name": bot.get("name", ""),
        "description": bot.get("description", ""),
        "is_deployed": bot.get("is_deployed", False),
    }


class BotSlugTokenRequest(BaseModel):
    conversation_type: str = "bot_session"


@router.post("/{slug}/token", response_model=TokenResponse)
async def mint_token_for_bot(slug: str, req: BotSlugTokenRequest):
    """
    Mint a LiveKit access token for a specific deployed bot.
    No user authentication required — the bot slug is the access key.
    """
    from app.modules.voice.application.session_service import create_voice_session

    bot = await _bot_repo.get_by_slug(slug)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")

    # Load realtime config
    config = await _config_repo.get_active()
    if not config:
        raise HTTPException(503, "Realtime transport not configured")

    user_id = f"user-{uuid.uuid4().hex[:8]}"

    try:
        result = await create_voice_session(
            bot=bot,
            user_id=user_id,
            conversation_type=req.conversation_type,
            config=config,
        )
    except ValueError as e:
        logger.error("[TOKEN] Session creation failed: %s", e)
        raise HTTPException(400, str(e))

    logger.info(
        "[TOKEN] Minted bot-slug token for session=%s bot=%s", result["session_id"], bot["name"]
    )
    return result
