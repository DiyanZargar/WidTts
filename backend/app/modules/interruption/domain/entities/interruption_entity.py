from dataclasses import dataclass
from typing import Optional


@dataclass
class Interruption:
    session_id: str
    interruption_type: str  # 'stop' | 'repeat' | 'correction' | 'answer' | 'end_conversation' | 'none'
    interruption_text: str
    timestamp: str
    turn_id: Optional[str] = None
    confidence: Optional[float] = None
