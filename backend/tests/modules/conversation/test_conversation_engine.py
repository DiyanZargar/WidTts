import pytest
import os
import json
from app.modules.conversation.infrastructure.external.json_conversation_repository import JsonConversationRepository
from app.modules.conversation.application.services.conversation_engine import ConversationEngine
from app.shared.exceptions.domain_exceptions import InvalidConversationSchemaError, DuplicateConversationIdError


def test_dynamic_json_script_loading():
    repo = JsonConversationRepository()
    engine = ConversationEngine(repo)

    available = repo.list_available()
    available_ids = [a["id"] for a in available]
    assert "daily_life_companion" in available_ids
    assert "career_life_advisor" in available_ids
    assert "health_wellness_assistant" in available_ids
    assert "travel_planner" in available_ids

    definition = engine.load_script("daily_life_companion")
    assert len(definition["questions"]) == 10
    assert engine.get_current("daily_life_companion", 0)["text"] == "What should I call you?"
    assert engine.is_complete("daily_life_companion", 10) is True


def test_invalid_json_schema_fails_startup(tmp_path):
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text(json.dumps({"id": "bad_pack"}), encoding="utf-8")  # missing required fields

    with pytest.raises(InvalidConversationSchemaError):
        JsonConversationRepository(definitions_dir=str(tmp_path))


def test_duplicate_conversation_id_fails_startup(tmp_path):
    valid_data = {
        "id": "dup_pack",
        "name": "Dup",
        "intro_line": "Hi",
        "questions": [{"sequence": 0, "type": "question", "text": "Q1", "expected_context": "c"}]
    }
    (tmp_path / "file1.json").write_text(json.dumps(valid_data), encoding="utf-8")
    (tmp_path / "file2.json").write_text(json.dumps(valid_data), encoding="utf-8")

    with pytest.raises(DuplicateConversationIdError):
        JsonConversationRepository(definitions_dir=str(tmp_path))
