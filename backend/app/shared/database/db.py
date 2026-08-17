"""
Async SQLite connection wrapper using aiosqlite.

Provides the same public API as the old asyncpg pool (get_connection,
get_transaction, close_pool) with a thin adapter that makes aiosqlite
rows behave like asyncpg Record objects (dict-like access).
"""

import os
import logging
import aiosqlite
from contextlib import asynccontextmanager
from typing import Optional, Any, List

from app.shared.config.settings import settings

logger = logging.getLogger("database")

_db_path: Optional[str] = None


def _get_db_path() -> str:
    """Resolve the SQLite database file path."""
    global _db_path
    if _db_path is None:
        _db_path = settings.db_path
        # Ensure parent directory exists
        db_dir = os.path.dirname(_db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
    return _db_path


class _RecordProxy:
    """Wraps an aiosqlite Row to behave like asyncpg.Record (dict-like access).

    Supports both row["col"] and row["col"] patterns, plus dict(row).
    """

    __slots__ = ("_row",)

    def __init__(self, row: aiosqlite.Row):
        self._row = row

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._row[key]
        return self._row[key]

    def __contains__(self, key):
        try:
            _ = self._row[key]
            return True
        except (KeyError, IndexError):
            return False

    def __iter__(self):
        # Iterate over column names
        return iter(self._row.keys())

    def __len__(self):
        return len(self._row.keys())

    def keys(self):
        return self._row.keys()

    def values(self):
        return [self._row[k] for k in self._row.keys()]

    def items(self):
        return [(k, self._row[k]) for k in self._row.keys()]

    def __repr__(self):
        return repr(dict(self))


class _ConnectionAdapter:
    """Wraps a raw aiosqlite connection with an asyncpg-style interface.

    Methods: fetchrow, fetch, execute, fetchval, transaction
    """

    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn
        self._conn.row_factory = aiosqlite.Row

    async def fetchrow(self, sql: str, *args) -> Optional[_RecordProxy]:
        """Return a single row as a RecordProxy, or None."""
        sql = _convert_placeholders(sql)
        cursor = await self._conn.execute(sql, args if args else None)
        row = await cursor.fetchone()
        if row is None:
            return None
        return _RecordProxy(row)

    async def fetch(self, sql: str, *args) -> List[_RecordProxy]:
        """Return all rows as a list of RecordProxy objects."""
        sql = _convert_placeholders(sql)
        cursor = await self._conn.execute(sql, args if args else None)
        rows = await cursor.fetchall()
        return [_RecordProxy(r) for r in rows]

    async def execute(self, sql: str, *args) -> str:
        """Execute SQL and return a status string like 'INSERT 0 1'.

        Does NOT auto-commit — callers must manage transactions explicitly
        via get_transaction() or conn.commit().
        """
        sql = _convert_placeholders(sql)
        cursor = await self._conn.execute(sql, args if args else None)
        # Mimic asyncpg status strings
        return f"{cursor.rowcount} rows affected"

    async def fetchval(self, sql: str, *args) -> Any:
        """Return a single scalar value (first column of first row)."""
        sql = _convert_placeholders(sql)
        cursor = await self._conn.execute(sql, args if args else None)
        row = await cursor.fetchone()
        if row is None:
            return None
        return row[0]

    @asynccontextmanager
    async def transaction(self):
        """Transaction context manager for aiosqlite.

        aiosqlite uses autocommit by default. We explicitly BEGIN/COMMIT/ROLLBACK.
        """
        await self._conn.execute("BEGIN")
        try:
            yield self
            await self._conn.commit()
        except Exception:
            await self._conn.rollback()
            raise


def _convert_placeholders(sql: str) -> str:
    """Convert $1, $2, ... positional placeholders to ? for SQLite.

    Also strips PostgreSQL-specific type casts like ::jsonb, ::uuid, ::text.
    """
    import re

    # Remove ::jsonb, ::uuid, ::text, ::integer, ::boolean casts
    # Pattern: a closing paren/quote/word-char followed by ::typename
    sql = re.sub(r"::(?:jsonb|uuid|text|integer|boolean|float|bigint|timestamptz|timestamp|bytea|int|int4|int8)", "", sql, flags=re.IGNORECASE)

    # Replace $N with ?
    def _replace(match):
        return "?"

    sql = re.sub(r"\$\d+", _replace, sql)
    return sql


@asynccontextmanager
async def get_connection():
    """Async context manager that yields an adapted aiosqlite connection.

    Commits on successful exit, rolls back on exception.
    """
    db_path = _get_db_path()
    conn = await aiosqlite.connect(db_path)
    # Enable WAL mode for better concurrency
    await conn.execute("PRAGMA journal_mode=WAL")
    # Enable foreign keys
    await conn.execute("PRAGMA foreign_keys=ON")
    adapter = _ConnectionAdapter(conn)
    try:
        yield adapter
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


@asynccontextmanager
async def get_transaction():
    """Async context manager that yields an adapted connection inside a transaction."""
    db_path = _get_db_path()
    conn = await aiosqlite.connect(db_path)
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    adapter = _ConnectionAdapter(conn)
    try:
        await conn.execute("BEGIN")
        yield adapter
        await conn.commit()
    except Exception:
        await conn.rollback()
        raise
    finally:
        await conn.close()


async def close_pool():
    """No-op for SQLite (connections are opened/closed per-request)."""
    logger.info("[DB] SQLite connection management is per-request (no pool to close)")
