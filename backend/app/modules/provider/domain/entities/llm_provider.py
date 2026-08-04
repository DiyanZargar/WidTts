"""
LLM Provider entity.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class LLMProvider:
    id: str
    name: str
    provider_type: str  # 'openai' | 'anthropic' | 'google' | 'openai_compatible'
    base_url: str = ""
    credentials_enc: Dict[str, Any] = field(default_factory=dict)
    key_version: int = 1
    available_models: List[str] = field(default_factory=list)
    last_test_status: str = "untested"
    last_test_at: Optional[datetime] = None
    is_default: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
