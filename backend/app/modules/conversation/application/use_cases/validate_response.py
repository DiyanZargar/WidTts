from typing import Dict, Any
from app.modules.conversation.domain.interfaces.validation_provider_interface import (
    ValidationProviderInterface,
)


class ValidateResponse:

    def __init__(self, validation_provider: ValidationProviderInterface):
        self._validation_provider = validation_provider

    async def execute(
        self, item_type: str, item_text: str, expected_context: str, user_response: str
    ) -> Dict[str, Any]:
        return await self._validation_provider.validate(
            item_type, item_text, expected_context, user_response
        )

    async def execute_stream(
        self, item_type: str, item_text: str, expected_context: str, user_response: str
    ):
        """Streaming validation yielding natural-language tokens + JSON metadata.
        Caller must split on '###METADATA###' to separate spoken text from JSON.
        """
        async for token in self._validation_provider.validate_stream(
            item_type, item_text, expected_context, user_response
        ):
            yield token

