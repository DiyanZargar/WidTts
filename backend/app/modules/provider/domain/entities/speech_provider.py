"""
Speech Provider entity — covers both STT and TTS config for a single provider.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class SpeechProvider:
    id: str
    name: str
    provider_type: str  # 'deepgram' | 'elevenlabs'
    credentials_enc: Dict[str, Any] = field(default_factory=dict)
    key_version: int = 1
    stt_model: str = ""
    stt_language: str = "en"
    stt_extra: Dict[str, Any] = field(default_factory=dict)
    tts_model: str = ""
    tts_voice_id: str = ""
    tts_extra: Dict[str, Any] = field(default_factory=dict)
    last_test_status: str = "untested"
    last_test_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
