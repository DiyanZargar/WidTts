from typing import AsyncGenerator
from app.modules.voice.domain.interfaces.tts_provider_interface import TTSProviderInterface


class SynthesizeSpeech:

    def __init__(self, tts_provider: TTSProviderInterface):
        self._tts_provider = tts_provider

    async def execute(self, text: str) -> bytes:
        return await self._tts_provider.synthesize(text)

    async def synthesize_stream(self, text: str):
        """Streaming synthesis yielding audio chunks as they arrive."""
        async for chunk in self._tts_provider.synthesize_stream(text):
            yield chunk

