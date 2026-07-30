import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    deepgram_api_key: str
    deepgram_tts_model: str
    
    # STT Parameters & Pattern (read strictly from env)
    deepgram_stt_base_url: str
    deepgram_stt_model_name: str
    deepgram_stt_enable_punctuation: bool
    deepgram_stt_enable_interim_transcripts: bool
    deepgram_stt_endpointing_silence_ms: int
    deepgram_stt_enable_smart_formatting: bool
    deepgram_stt_url_pattern: str
    
    openai_api_key: str
    openai_base_url: str
    ai_validation_model: str
    
    database_path: str
    max_retries_per_item: Optional[int] = None
    conversation_definitions_dir: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def deepgram_stt_url(self) -> str:
        env_url = os.getenv("DEEPGRAM_STT_URL")
        if env_url and "?" in env_url and "model=" in env_url:
            return env_url
            
        # Smart detection: flux models belong to Deepgram v2/listen and do not accept v1 query params
        if "flux" in self.deepgram_stt_model_name.lower():
            base_url = "wss://api.deepgram.com/v2/listen" if "v1" in self.deepgram_stt_base_url else self.deepgram_stt_base_url
            return f"{base_url}?model={self.deepgram_stt_model_name}"

        kwargs = {
            "base_url": self.deepgram_stt_base_url,
            "model": self.deepgram_stt_model_name,
            "punctuate": str(self.deepgram_stt_enable_punctuation).lower(),
            "interim_transcripts": str(self.deepgram_stt_enable_interim_transcripts).lower(),
            "endpointing_ms": self.deepgram_stt_endpointing_silence_ms,
            "smart_formatting": str(self.deepgram_stt_enable_smart_formatting).lower(),
        }
        try:
            return self.deepgram_stt_url_pattern.format(**kwargs)
        except (KeyError, ValueError):
            return f"{self.deepgram_stt_base_url}?model={self.deepgram_stt_model_name}"


settings = Settings()
