import json
import re
import asyncio
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from app.shared.logging.logger import logger
from app.modules.interruption.infrastructure.external.prompts import (
    INTERRUPTION_SYSTEM_PROMPT,
    build_interruption_user_message,
)

VALID_TYPES = {"STOP", "REPEAT", "CORRECTION", "ANSWER", "END_CONVERSATION", "NONE"}


class InterruptionClassifierAdapter:
    """LLM-based interruption intent classifier.

    Classifies user speech that arrives during or immediately after TTS playback
    into one of: STOP, REPEAT, CORRECTION, ANSWER, END_CONVERSATION, NONE.
    """

    def __init__(self):
        self._client: Optional[AsyncOpenAI] = None
        self._llm_config: Optional[Dict[str, Any]] = None

    def set_llm_config(self, config: Dict[str, Any]) -> None:
        """Inject LLM config from bot at session startup."""
        self._llm_config = config
        self._client = None

    def _get_client(self) -> AsyncOpenAI:
        if not self._client:
            api_key = "dummy_key"
            base_url = "https://api.openai.com/v1"
            if self._llm_config:
                api_key = self._llm_config.get("api_key", api_key)
                base_url = self._llm_config.get("base_url", base_url) or base_url
            self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        return self._client

    def _get_model(self) -> str:
        if self._llm_config:
            return self._llm_config.get("model", "gpt-4o-mini")
        return "gpt-4o-mini"

    async def classify(
        self,
        transcript: str,
        current_question: str = "",
        tts_text: str = "",
        expected_context: str = "",
        previous_answer: Optional[str] = None,
        is_tts_playing: bool = False,
    ) -> Dict[str, Any]:
        """Classify interruption intent using the LLM.

        Returns dict with keys: interrupt (bool), type (str), confidence (float).
        On failure, returns a safe default of NONE.
        """
        user_content = build_interruption_user_message(
            transcript=transcript,
            current_question=current_question,
            tts_text=tts_text,
            expected_context=expected_context,
            previous_answer=previous_answer or "",
            is_tts_playing=is_tts_playing,
        )

        client = self._get_client()

        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self._get_model(),
                    messages=[
                        {"role": "system", "content": INTERRUPTION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    max_tokens=256,
                    timeout=8,
                ),
                timeout=10.0,
            )

            choice = response.choices[0]
            msg = choice.message
            text = msg.content or ""

            # Strip markdown fences if present
            text = text.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            # Extract JSON from response
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                text = match.group(0)

            parsed = json.loads(text)

            interrupt = bool(parsed.get("interrupt", False))
            itype = str(parsed.get("type", "NONE")).upper()
            confidence = float(parsed.get("confidence", 0.5))

            # Validate type
            if itype not in VALID_TYPES:
                logger.warning(
                    f"[INTERRUPT CLASSIFY] Invalid type '{itype}' from LLM, defaulting to NONE"
                )
                itype = "NONE"
                interrupt = False

            logger.info(
                f"[INTERRUPT CLASSIFY] LLM classified: type={itype} "
                f"confidence={confidence:.2f} interrupt={interrupt} "
                f"transcript='{transcript[:60]}'"
            )

            return {
                "interrupt": interrupt,
                "type": itype,
                "confidence": confidence,
            }

        except (asyncio.TimeoutError, Exception) as e:
            is_timeout = isinstance(e, asyncio.TimeoutError)
            logger.warning(
                f"[INTERRUPT CLASSIFY {'TIMEOUT' if is_timeout else 'ERROR'}] "
                f"LLM unavailable for: '{transcript[:60]}' — {e}. "
                f"Defaulting to NONE."
            )
            return {
                "interrupt": False,
                "type": "NONE",
                "confidence": 0.0,
            }
