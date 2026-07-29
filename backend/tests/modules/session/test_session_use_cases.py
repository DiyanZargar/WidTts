import pytest
from app.shared.config.settings import settings


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "database_path", db_path)
    from app.shared.database.init_db import init_db
    init_db()
    yield


def test_session_lifecycle():
    from app.modules.session.infrastructure.persistence.sqlite_session_repository import SqliteSessionRepository
    from app.modules.session.application.use_cases.create_session import CreateSession
    from app.modules.session.application.use_cases.get_session import GetSession
    from app.modules.session.application.use_cases.pause_session import PauseSession
    from app.modules.session.application.use_cases.close_session import CloseSession
    from app.modules.session.application.use_cases.update_pointer import UpdatePointer

    repo = SqliteSessionRepository()
    create = CreateSession(repo)
    get = GetSession(repo)
    pause = PauseSession(repo)
    close = CloseSession(repo)
    update = UpdatePointer(repo)

    create.execute("s-123", "daily_life_companion")
    s = get.execute("s-123")
    assert s["status"] == "active"
    assert s["conversation_type"] == "daily_life_companion"

    update.execute("s-123", 2, "asking", 1)
    s = get.execute("s-123")
    assert s["current_question_index"] == 2
    assert s["retries"] == 1

    pause.execute("s-123")
    s = get.execute("s-123")
    assert s["status"] == "paused"

    close.execute("s-123", "completed")
    s = get.execute("s-123")
    assert s["status"] == "completed"
