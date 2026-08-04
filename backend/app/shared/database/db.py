"""
Async PostgreSQL connection pool using asyncpg.

Replaces the old SQLite db.py. Provides a lazy-initialized singleton pool
and a checkout context manager for use across all repositories.
"""

import asyncpg
import logging
from contextlib import asynccontextmanager
from typing import Optional

from app.shared.config.settings import settings

logger = logging.getLogger("database")

_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Lazy-initialize and return the global connection pool."""
    global _pool
    if _pool is None:
        logger.info(f"[DB] Creating asyncpg pool → {settings.database_url.split('@')[-1]}")
        _pool = await asyncpg.create_pool(
            dsn=settings.database_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("[DB] Connection pool created successfully")
    return _pool


@asynccontextmanager
async def get_connection():
    """Checkout a connection from the pool."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def get_transaction():
    """Checkout a connection and start a transaction."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


async def close_pool():
    """Gracefully close the pool on shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("[DB] Connection pool closed")
