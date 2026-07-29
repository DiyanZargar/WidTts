from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("context_manager")


@dataclass
class MessageEntry:
    role: str
    content: str
    timestamp: float
    turn_id: Optional[str] = None


class ContextManager:
    """Manages conversation history, token budget, and prompt construction."""

    CHARS_PER_TOKEN = 4

    def __init__(self, max_tokens: int = 4000):
        self.max_tokens = max_tokens
        self._sessions: Dict[str, List[MessageEntry]] = {}

    def add_message(self, session_id: str, role: str, content: str, turn_id: Optional[str] = None) -> None:
        if not session_id:
            return
        history = self._sessions.setdefault(session_id, [])
        import time
        entry = MessageEntry(role=role, content=content, timestamp=time.time(), turn_id=turn_id)
        history.append(entry)
        self._prune_if_needed(session_id)

    def get_history(self, session_id: str) -> List[MessageEntry]:
        return list(self._sessions.get(session_id, []))

    def get_recent(self, session_id: str, count: int = 10) -> List[MessageEntry]:
        history = self._sessions.get(session_id, [])
        return history[-count:] if len(history) > count else list(history)

    def build_validation_prompt(self, session_id: str, question_type: str, question_text: str,
                              expected_context: str, user_transcript: str, max_history: int = 6) -> str:
        recent = self.get_recent(session_id, max_history)
        history_lines = []
        for msg in recent:
            label = "User" if msg.role == "user" else ("Assistant" if msg.role == "assistant" else "System")
            history_lines.append(f"{label}: {msg.content}")
        history_block = "\n".join(history_lines) if history_lines else "No previous messages."

        return (
            "You are evaluating a user's response in a structured interview.\n\n"
            "## Conversation History\n" + history_block + "\n\n"
            "## Current Question\n"
            f"Type: {question_type}\n"
            f"Question: {question_text}\n"
            f"Expected Context: {expected_context}\n\n"
            "## User's Response\n" + user_transcript + "\n\n"
            "Evaluate whether the response is valid and should advance to the next question.\n\n"
            "Respond with natural language feedback first, then ###METADATA###, then JSON with:\n"
            '- classification: "VALID" | "NEEDS_CLARIFICATION" | "OFF_TOPIC" | "INCOMPLETE"\n'
            "- should_advance: bool\n"
            "- reason: human-friendly explanation\n"
            "- relevance: float 0-1\n"
            "- completeness: float 0-1\n"
        )

    def build_interruption_prompt(self, session_id: str, transcript: str, current_question: str,
                                  tts_text: str, expected_context: str) -> str:
        recent = self.get_recent(session_id, 4)
        history_lines = [f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}" for m in recent]
        history_block = "\n".join(history_lines) if history_lines else "No context."

        return (
            "Classify the user's intent during an ongoing conversation.\n\n"
            "## Recent Context\n" + history_block + "\n\n"
            f"## Current Question\n{current_question}\n\n"
            f"## What the assistant is saying\n{tts_text}\n\n"
            f"## User just said\n{transcript}\n\n"
            "Classify the intent. Respond ONLY with JSON:\n"
            '{"interrupt": bool, "type": "STOP" | "REPEAT" | "CORRECTION" | "ANSWER" | "END_CONVERSATION" | "NONE", "confidence": float}\n'
        )

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _prune_if_needed(self, session_id: str) -> None:
        history = self._sessions.get(session_id, [])
        if not history:
            return
        total_chars = sum(len(m.content) for m in history)
        estimated_tokens = total_chars // self.CHARS_PER_TOKEN
        if estimated_tokens > self.max_tokens:
            logger.info(f"[CONTEXT] Pruning session {session_id}: ~{estimated_tokens} tokens > {self.max_tokens}")
            while estimated_tokens > self.max_tokens and len(history) > 2:
                for i, msg in enumerate(history):
                    if msg.role != "system":
                        history.pop(i)
                        break
                else:
                    history.pop(0)
                total_chars = sum(len(m.content) for m in history)
                estimated_tokens = total_chars // self.CHARS_PER_TOKEN
