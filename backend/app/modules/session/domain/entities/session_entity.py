from dataclasses import dataclass
from typing import Optional


@dataclass
class Session:
    session_id: str
    user_id: str
    start_time: str
    end_time: Optional[str]
    conversation_type: str
    status: str  # 'active' | 'paused' | 'completed' | 'cancelled'
    current_question_index: int
    current_state: str
    retries: int
