from typing import Optional, Dict, Any
from app.modules.conversation.domain.interfaces.conversation_repository_interface import (
    ConversationRepositoryInterface,
)


class ConversationEngine:

    def __init__(self, conversation_repository: ConversationRepositoryInterface):
        self._conversation_repository = conversation_repository

    def load_script(self, conversation_type: str) -> Dict[str, Any]:
        """Loads definition from repository cache. Contains ZERO hardcoded conversation data."""
        return self._conversation_repository.get_by_id(conversation_type)

    def get_intro_line(self, conversation_type: str) -> str:
        definition = self._conversation_repository.get_by_id(conversation_type)
        return definition.get("intro_line", "Welcome to the conversation.")

    def get_current(self, conversation_type: str, index: int) -> Optional[Dict[str, Any]]:
        definition = self._conversation_repository.get_by_id(conversation_type)
        questions = definition.get("questions", [])
        return questions[index] if index < len(questions) else None

    def is_complete(self, conversation_type: str, index: int) -> bool:
        definition = self._conversation_repository.get_by_id(conversation_type)
        questions = definition.get("questions", [])
        return index >= len(questions)

    def generate_human_transition(self, prev_item: Optional[Dict[str, Any]], user_transcript: str) -> str:
        """Generates a warm, natural human bridge based on the user's turn."""
        if not prev_item or not user_transcript:
            return ""

        cleaned = user_transcript.strip()
        ctx = prev_item.get("expected_context", "").lower()
        question_text = prev_item.get("text", "").lower()

        # 1. Name / Call You context
        if "name" in ctx or "call you" in question_text or "name" in question_text:
            words = [w for w in cleaned.split() if w.lower() not in ("i", "am", "my", "name", "is", "im", "call", "me")]
            name = words[-1].capitalize() if words else "there"
            return f"Nice to meet you, {name}! "

        # 2. Conversational acknowledgments
        cleaned_lower = cleaned.lower()
        if any(w in cleaned_lower for w in ["no", "not really", "didn't", "dont", "don't", "none"]):
            return "Got it. "
        if any(w in cleaned_lower for w in ["yes", "yeah", "sure", "great", "good", "fine", "did"]):
            return "Awesome! "

        return "Understood! "
