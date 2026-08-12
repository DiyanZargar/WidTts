"""
Database initialization hook.

Called at application startup to ensure SQLite schema is up to date
and default seed configurations (e.g. Local Docker realtime transport) are present.
"""

import logging
from app.shared.database.migrations_sqlite import run_migrations_sqlite

logger = logging.getLogger("init_db")


async def seed_default_realtime_config():
    """Ensure default Local Docker realtime transport config exists if none present."""
    try:
        from app.modules.voice.infrastructure.persistence.realtime_config_repository import RealtimeConfigRepository
        from app.shared.security.envelope_encryption import encrypt_and_store
        from app.shared.config.settings import settings

        repo = RealtimeConfigRepository()
        all_configs = await repo.get_all()
        if not all_configs:
            encrypted_key_blob, key_version = await encrypt_and_store({"value": settings.livekit_api_key})
            encrypted_secret_blob, _ = await encrypt_and_store({"value": settings.livekit_api_secret})

            # Wrap in {blob, key_version} format expected by token routes
            await repo.create({
                "name": "Environment Transport",
                "provider_type": "livekit",
                "server_url": settings.livekit_url,
                "encrypted_api_key": {"blob": encrypted_key_blob, "key_version": key_version},
                "encrypted_api_secret": {"blob": encrypted_secret_blob, "key_version": key_version},
                "room_token_ttl_seconds": settings.livekit_token_ttl_seconds,
                "audio_sample_rate": settings.livekit_audio_sample_rate,
                "is_active": True,
            })
            logger.info("[INIT_DB] Seeded default realtime transport configuration from .env settings")
    except Exception as e:
        logger.warning(f"[INIT_DB] Realtime config seed warning: {e}")


async def init_db():
    """Initialize database: run migrations.

    Note: seed_default_realtime_config() is NOT called here because it
    requires the encryption key to be bootstrapped first. Call
    seed_default_realtime_config() separately after bootstrap_encryption_key().
    """
    logger.info("Initializing SQLite database...")

    logger.info("Running pending migrations...")
    await run_migrations_sqlite()

    logger.info("Database initialization complete")
