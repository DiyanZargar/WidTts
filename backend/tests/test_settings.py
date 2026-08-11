"""Tests for application settings defaults and aliases."""
import pytest
from app.shared.config.settings import Settings


class TestSettingsDefaults:
    def test_default_postgres_user(self):
        s = Settings()
        assert s.postgres_user == "widtts"

    def test_default_postgres_host(self):
        s = Settings()
        assert s.postgres_host == "localhost"

    def test_default_postgres_port(self):
        s = Settings()
        assert s.postgres_port == 5432

    def test_default_livekit_url(self):
        s = Settings()
        assert s.livekit_url == "ws://localhost:7880"

    def test_default_livekit_api_key(self):
        s = Settings()
        assert s.livekit_api_key == "devkey"

    def test_default_room_inactivity_timeout(self):
        s = Settings()
        assert s.room_inactivity_timeout_seconds == 30

    def test_default_agent_token_ttl(self):
        s = Settings()
        assert s.agent_token_ttl_seconds == 7200

    def test_default_port(self):
        s = Settings()
        assert s.port == 8000

    def test_master_encryption_key_is_string(self):
        s = Settings()
        assert isinstance(s.master_encryption_key, str)

    def test_database_url_from_components(self):
        s = Settings()
        url = s.database_url
        assert "postgresql://" in url
        assert "widtts" in url
        assert "localhost" in url
        assert "5432" in url

    def test_database_url_template_expansion(self):
        s = Settings(DATABASE_URL="postgresql://${POSTGRES_USER}:***@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}")
        url = s.database_url
        assert "widtts" in url
        assert "localhost" in url
        assert "5432" in url

    def test_database_url_raw_override(self):
        s = Settings(DATABASE_URL="postgresql://custom:pass@dbhost:5433/mydb")
        url = s.database_url
        assert url == "postgresql://custom:pass@dbhost:5433/mydb"
