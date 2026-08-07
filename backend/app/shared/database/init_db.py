"""
Database initialization hook.

Called at application startup to ensure PostgreSQL schema is up to date
and default seed configurations (e.g. Local Docker realtime transport) are present.
"""

import logging
from app.shared.database.migrations_pg import run_migrations_pg
from app.shared.database.db import get_pool

logger = logging.getLogger("init_db")


async def seed_default_realtime_config():
    """Ensure default Local Docker realtime transport config exists if none present."""
    try:
        from app.modules.voice.infrastructure.persistence.realtime_config_repository import RealtimeConfigRepository
        from app.shared.security.envelope_encryption import encrypt_and_store

        repo = RealtimeConfigRepository()
        active = await repo.get_active()
        if not active:
            encrypted_key, _ = await encrypt_and_store({"value": "devkey"})
            encrypted_secret, _ = await encrypt_and_store({"value": "secret"})

            await repo.create({
                "name": "Local Docker",
                "provider_type": "livekit",
                "server_url": "ws://localhost:7880",
                "encrypted_api_key": encrypted_key,
                "encrypted_api_secret": encrypted_secret,
                "room_token_ttl_seconds": 3600,
                "audio_sample_rate": 16000,
                "is_active": True,
            })
            logger.info("[INIT_DB] Seeded default Local Docker realtime transport configuration")
    except Exception as e:
        logger.warning(f"[INIT_DB] Realtime config seed warning: {e}")


async def init_db():
    """Initialize database: create pool, run migrations, and seed defaults."""
    logger.info("Initializing PostgreSQL connection pool...")
    await get_pool()

    logger.info("Running pending migrations...")
    await run_migrations_pg()

    logger.info("Seeding default transport configuration...")
    await seed_default_realtime_config()

    logger.info("Database initialization complete")
