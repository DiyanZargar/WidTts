"""
Database initialization hook.

Called at application startup to ensure PostgreSQL schema is up to date.
"""

from app.shared.database.migrations_pg import run_migrations_pg
from app.shared.database.db import get_pool
import logging

logger = logging.getLogger("init_db")


async def init_db():
    """Initialize database: create pool and run pending migrations."""
    logger.info("Initializing PostgreSQL connection pool...")
    await get_pool()

    logger.info("Running pending migrations...")
    await run_migrations_pg()

    logger.info("Database initialization complete")
