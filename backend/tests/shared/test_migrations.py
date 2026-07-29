import sqlite3
import pytest
from app.shared.config.settings import settings


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "database_path", db_path)
    yield db_path


def test_migrations_create_all_tables(fresh_db):
    from app.shared.database.init_db import init_db
    init_db()
    conn = sqlite3.connect(fresh_db)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    expected = {"sessions", "messages", "responses", "interruptions", "schema_migrations"}
    assert expected.issubset(tables)


def test_migrations_are_idempotent(fresh_db):
    from app.shared.database.init_db import init_db
    init_db()
    init_db()  # second run should not raise
    conn = sqlite3.connect(fresh_db)
    count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    conn.close()
    assert count == 5
