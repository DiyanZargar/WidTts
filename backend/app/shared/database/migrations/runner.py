import os
import sqlite3
from app.shared.config.settings import settings


def run_migrations():
    migration_dir = os.path.dirname(__file__)
    conn = sqlite3.connect(settings.database_path)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()

    applied = {
        row[0]
        for row in conn.execute("SELECT filename FROM schema_migrations").fetchall()
    }

    sql_files = sorted(f for f in os.listdir(migration_dir) if f.endswith(".sql"))

    for filename in sql_files:
        if filename in applied:
            continue
        filepath = os.path.join(migration_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            sql = f.read()
        conn.executescript(sql)
        conn.execute(
            "INSERT INTO schema_migrations (filename) VALUES (?)", (filename,)
        )
        conn.commit()
        print(f"Applied migration: {filename}")

    conn.close()
