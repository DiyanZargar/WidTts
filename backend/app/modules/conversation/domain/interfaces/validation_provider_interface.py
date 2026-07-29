from typing import Dict, Any, AsyncGenerator
from abc import ABC, abstractmethod


class ValidationProviderInterface(ABC):

    @abstractmethod
    async def validate(
        self, item_type: str, item_text: str, expected_context: str, user_response: str
    ) -> Dict[str, Any]:
        """Validate user response turn against active question and expected context.
        Blocking full-response validation (backward compatible)."""
        raise NotImplementedError

    @abstractmethod
    async def validate_stream(
        self, item_type: str, item_text: str, expected_context: str, user_response: str
    ):
        """Streaming validation yielding natural-language tokens as they arrive.
        After the spoken text, yields the JSON metadata block prefixed by a delimiter.
        Caller must split on '###METADATA###' to separate spoken text from JSON.
        """
        raise NotImplementedError

