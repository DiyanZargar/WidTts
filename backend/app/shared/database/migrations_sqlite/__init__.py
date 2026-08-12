"""
Async SQLite migration runner.

Reads .sql files from the migrations_sqlite/ directory and applies them
in alphabetical order, tracking applied migrations in a schema_migrations table.
"""

import os
import logging
from app.shared.database.db import get_connection

logger = logging.getLogger("migrations")


async def run_migrations_sqlite():
    """Execute all pending SQL migrations against SQLite."""
    migration_dir = os.path.dirname(__file__)

    async with get_connection() as conn:
        # Create tracking table if it doesn't exist
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Get already-applied migrations
        rows = await conn.fetch("SELECT filename FROM schema_migrations")
        applied = {row["filename"] for row in rows}

        # Find and sort SQL files
        sql_files = sorted(
            f for f in os.listdir(migration_dir)
            if f.endswith(".sql")
        )

        for filename in sql_files:
            if filename in applied:
                continue

            filepath = os.path.join(migration_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                sql = f.read()

            # Execute migration
            async with conn.transaction():
                for statement in sql.split(";"):
                    stmt = statement.strip()
                    if stmt:
                        await conn.execute(stmt)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES (?)",
                    filename,
                )

            logger.info(f"[MIGRATION] Applied: {filename}")

    logger.info("[MIGRATION] All migrations up to date")
