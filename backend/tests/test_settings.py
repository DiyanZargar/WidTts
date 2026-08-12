"""Tests for application settings defaults and aliases."""
import os
import pytest
from app.shared.config.settings import Settings


@pytest.fixture(autouse=False)
def clean_env(monkeypatch):
    """Remove container/Docker environment variables so defaults are testable."""
    for var in [
        "DB_PATH", "LIVEKIT_URL", "LIVEKIT_INTERNAL_URL", "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET", "MASTER_ENCRYPTION_KEY", "APP_SECRET",
        "PORT", "ROOM_INACTIVITY_TIMEOUT_SECONDS", "AGENT_TOKEN_TTL_SECONDS",
    ]:
        monkeypatch.delenv(var, raising=False)


class TestSettingsDefaults:
    @pytest.mark.usefixtures("clean_env")
    def test_default_db_path(self):
        s = Settings()
        assert s.db_path == "data/widtts.db"

    @pytest.mark.usefixtures("clean_env")
    def test_default_livekit_url(self):
        s = Settings()
        assert s.livekit_url == "ws://localhost:7880"

    @pytest.mark.usefixtures("clean_env")
    def test_default_livekit_api_key(self):
        s = Settings()
        assert s.livekit_api_key == "devkey"

    @pytest.mark.usefixtures("clean_env")
    def test_default_room_inactivity_timeout(self):
        s = Settings()
        assert s.room_inactivity_timeout_seconds == 30

    @pytest.mark.usefixtures("clean_env")
    def test_default_agent_token_ttl(self):
        s = Settings()
        assert s.agent_token_ttl_seconds == 7200

    @pytest.mark.usefixtures("clean_env")
    def test_default_port(self):
        s = Settings()
        assert s.port == 8000

    @pytest.mark.usefixtures("clean_env")
    def test_master_encryption_key_is_string(self):
        s = Settings()
        assert isinstance(s.master_encryption_key, str)

    @pytest.mark.usefixtures("clean_env")
    def test_livekit_internal_url_default_none(self):
        s = Settings()
        assert s.livekit_internal_url is None
