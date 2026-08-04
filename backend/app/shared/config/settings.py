import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Platform infrastructure settings.

    All provider credentials (Deepgram, ElevenLabs, OpenAI, etc.) are now stored
    in PostgreSQL with envelope encryption and managed through the Admin UI.

    Only infrastructure secrets that the app needs before the database is available
    are kept here.
    """

    # ── PostgreSQL ──
    database_url: str = "postgresql://widtts:widtts_dev_password@localhost:5432/widtts"

    # ── Envelope Encryption ──
    # Base64-encoded 32-byte AES-256 master key for wrapping DEKs.
    # Generate with: python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"
    master_encryption_key: str = ""

    # ── Application ──
    app_secret: str = "dev-secret-change-in-production"
    port: int = 8000

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
