import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    deepgram_api_key: str
    deepgram_tts_model: str
    deepgram_stt_url: str
    
    openai_api_key: str
    openai_base_url: str
    ai_validation_model: str
    
    database_path: str = "app.db"
    max_retries_per_item: Optional[int] = None
    conversation_definitions_dir: str = os.path.join("app", "conversation_definitions")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
