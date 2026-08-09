"""
Bot entity.

A bot is the central entity: identity + LLM config + speech provider config + system prompt.
"""

from dataclasses import dataclass, field
from typing import List, Optional
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
    stt_model: str = ""
    tts_model: str = ""
    stt_languages: List[str] = field(default_factory=lambda: ["en"])
    stt_primary_language: str = "en"
    tts_languages: List[str] = field(default_factory=lambda: ["en"])
    tts_primary_language: str = "en"
    is_active: bool = False
    deploy_slug: Optional[str] = None
    is_deployed: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
