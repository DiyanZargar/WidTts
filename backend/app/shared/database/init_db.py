from app.shared.database.migrations.runner import run_migrations


def init_db():
    run_migrations()
