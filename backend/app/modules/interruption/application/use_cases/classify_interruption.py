from typing import Optional, Dict, Any
from app.shared.logging.logger import logger
from app.modules.interruption.infrastructure.external.interruption_classifier_adapter import InterruptionClassifierAdapter


class ClassifyInterruption:
    """Classifies interruption intent using LLM-based semantic analysis.

    Deterministic routing is used ONLY for clear system commands
    (stop, end, cancel) for low-latency response. All semantic
    interpretation of conversational interruptions comes from the LLM.
    """

    # Deterministic system commands — matched exactly for instant response.
    # These bypass the LLM to guarantee sub-100ms handling.
    _STOP_COMMANDS = {"stop", "stop talking", "be quiet", "shut up", "pause"}
    _END_COMMANDS = {"end", "end conversation", "start over", "reset", "quit", "i'm done"}

    def __init__(self, classifier_adapter: Optional[InterruptionClassifierAdapter] = None):
        self._adapter = classifier_adapter

    async def execute(
        self,
        transcript: str,
        current_question: str = "",
        tts_text: str = "",
        expected_context: str = "",
        previous_answer: Optional[str] = None,
        is_tts_playing: bool = False,
    ) -> Dict[str, Any]:
        """Classify the interruption intent of a user transcript.

        Returns dict: {"interrupt": bool, "type": str, "confidence": float}
        Types: STOP, REPEAT, CORRECTION, ANSWER, END_CONVERSATION, NONE
        """
        t = transcript.strip().lower()

        # ── Deterministic routing for system commands ──
        # These are infrastructure-level commands that need instant response.
        if t in self._STOP_COMMANDS:
            logger.info(f"[INTERRUPT DETECTISTOP] Deterministic match: '{t}'")
            return {"interrupt": True, "type": "STOP", "confidence": 1.0}

        if t in self._END_COMMANDS:
            logger.info(f"[INTERRUPT DETECTISTOP END] Deterministic match: '{t}'")
            return {"interrupt": True, "type": "END_CONVERSATION", "confidence": 1.0}

        # ── LLM-based semantic classification ──
        if self._adapter:
            return await self._adapter.classify(
                transcript=transcript,
                current_question=current_question,
                tts_text=tts_text,
                expected_context=expected_context,
                previous_answer=previous_answer,
                is_tts_playing=is_tts_playing,
            )

        # ── No adapter configured — safe default ──
        logger.warning("[INTERRUPT CLASSIFY] No classifier adapter configured, defaulting to NONE")
        return {"interrupt": False, "type": "NONE", "confidence": 0.0}
