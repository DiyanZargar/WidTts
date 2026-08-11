import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    Platform infrastructure settings.

    PostgreSQL connection parameters can be configured individually via
    POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB,
    or via a DATABASE_URL template in .env.
    """

    # ── PostgreSQL Component Variables ──
    postgres_user: str = Field(default="widtts", alias="POSTGRES_USER")
    postgres_password: str = Field(default="widtts_dev_password", alias="POSTGRES_PASSWORD")
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="widtts", alias="POSTGRES_DB")

    # Raw DATABASE_URL environment variable (may contain ${VAR} templates)
    raw_database_url: Optional[str] = Field(default=None, alias="DATABASE_URL")

    @property
    def database_url(self) -> str:
        """
        Dynamically resolves the PostgreSQL DSN connection string.

        Expands template variables (${POSTGRES_USER}, etc.) if present in DATABASE_URL,
        or constructs DSN from component variables.
        """
        if self.raw_database_url:
            # Set environment variables for template expansion
            env = os.environ.copy()
            env["POSTGRES_USER"] = self.postgres_user
            env["POSTGRES_PASSWORD"] = self.postgres_password
            env["POSTGRES_HOST"] = self.postgres_host
            env["POSTGRES_PORT"] = str(self.postgres_port)
            env["POSTGRES_DB"] = self.postgres_db

            # Expand ${VAR} in raw_database_url
            url = self.raw_database_url
            for k, v in env.items():
                url = url.replace(f"${{{k}}}", str(v)).replace(f"${k}", str(v))

            if not url.startswith("${"):
                return url

        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    # ── Envelope Encryption ──
    # Base64-encoded 32-byte AES-256 master key for wrapping DEKs.
    master_encryption_key: str = ""

    # ── Realtime Voice Transport (LiveKit) ──
    livekit_url: str = Field(default="ws://localhost:7880", alias="LIVEKIT_URL")
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
