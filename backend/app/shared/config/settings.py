import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    Platform infrastructure settings.

    SQLite database path is configurable via DB_PATH env var.
    """

    # ── SQLite Database ──
    db_path: str = Field(default="data/widtts.db", alias="DB_PATH")

    # ── Envelope Encryption ──
    # Base64-encoded 32-byte AES-256 master key for wrapping DEKs.
    master_encryption_key: str = ""

    # ── Realtime Voice Transport (LiveKit) ──
    livekit_url: str = Field(default="ws://localhost:7880", alias="LIVEKIT_URL")
    livekit_internal_url: Optional[str] = Field(default=None, alias="LIVEKIT_INTERNAL_URL")
    livekit_api_key: str = Field(default="devkey", alias="LIVEKIT_API_KEY")
    livekit_api_secret: str = Field(default="secret", alias="LIVEKIT_API_SECRET")
    livekit_token_ttl_seconds: int = Field(default=3600, alias="LIVEKIT_TOKEN_TTL_SECONDS")
    livekit_audio_sample_rate: int = Field(default=16000, alias="LIVEKIT_AUDIO_SAMPLE_RATE")

    # ── Application ──
    app_secret: str = "dev-secret-change-in-production"
    port: int = 8000
    room_inactivity_timeout_seconds: float = Field(default=30, alias="ROOM_INACTIVITY_TIMEOUT_SECONDS")
    agent_token_ttl_seconds: int = Field(default=7200, alias="AGENT_TOKEN_TTL_SECONDS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
