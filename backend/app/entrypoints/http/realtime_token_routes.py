"""
Realtime Token route.

Mints a LiveKit AccessToken scoped to a per-session room.
Also starts the LiveKit session adapter as a background task.
No LiveKit terminology appears in any response field name.
"""

import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.shared.security.token_service import verify_token, AuthenticationError
from app.modules.voice.infrastructure.persistence.realtime_config_repository import (
    RealtimeConfigRepository,
)
from app.modules.bot.infrastructure.persistence.bot_repository import (
    BotRepository,
)
from app.shared.schemas import TokenResponse

logger = logging.getLogger("realtime_token")
router = APIRouter(prefix="/realtime", tags=["realtime"])

_config_repo = RealtimeConfigRepository()
_bot_repo = BotRepository()


class TokenRequest(BaseModel):
    conversation_type: str = "active_bot"


@router.post("/token", response_model=TokenResponse)
async def mint_realtime_token(req: TokenRequest, authorization: str = ""):
    """
    Mint a realtime access token for the current user.
    Creates a new session and starts the LiveKit session adapter.
    """
    from app.modules.voice.application.session_service import create_voice_session

    # Authenticate user
    token_str = authorization.replace("Bearer ", "") if authorization else None
    try:
        user_id = verify_token(token_str)
    except AuthenticationError as e:
        raise HTTPException(401, f"Authentication failed: {e}")

    # Load realtime config
    config = await _config_repo.get_active()
    if not config:
        raise HTTPException(503, "Realtime transport not configured")

    # Load active bot
    bot = await _bot_repo.get_active()
    if not bot:
        raise HTTPException(503, "No active bot configured")

    try:
        result = await create_voice_session(
            bot=bot,
            user_id=user_id,
            conversation_type=req.conversation_type,
            config=config,
        )
    except ValueError as e:
        logger.error("[TOKEN] Session creation failed: %s", e)
        raise HTTPException(500, str(e))

    logger.info("[TOKEN] Minted token for session=%s room=%s", result["session_id"], result["room_name"])
    return result
