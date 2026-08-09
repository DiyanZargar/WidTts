"""
Bot entity.

A bot is the central entity: identity + LLM config + speech provider config + system prompt.
"""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class Bot:
    id: str
    name: str
    description: str = ""
    personality: str = ""
    system_prompt: str = ""
    llm_provider_id: Optional[str] = None
    llm_model: str = ""
    stt_provider_id: Optional[str] = None
    tts_provider_id: Optional[str] = None
    is_active: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
