import json
import os
from typing import Optional, Dict, Any, List
from pydantic import ValidationError

from app.shared.config.settings import settings
from app.shared.schemas.conversation_schema import ConversationDefinitionSchema
from app.shared.exceptions.domain_exceptions import (
    ConversationTypeNotFoundError,
    InvalidConversationSchemaError,
    DuplicateConversationIdError,
)
from app.modules.conversation.domain.interfaces.conversation_repository_interface import (
    ConversationRepositoryInterface,
)


class JsonConversationRepository(ConversationRepositoryInterface):

    def __init__(self, definitions_dir: Optional[str] = None):
        if definitions_dir is None:
            definitions_dir = settings.conversation_definitions_dir
        if not os.path.isabs(definitions_dir):
            # Navigate from app/modules/conversation/infrastructure/external up 5 levels to backend root
            backend_root = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
            )
            definitions_dir = os.path.join(backend_root, definitions_dir)
        self._definitions_dir = definitions_dir
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.initialize()

    def initialize(self) -> None:
        """Scan directory, validate schemas, ensure unique IDs, and cache in memory."""
        self._cache.clear()

        if not os.path.exists(self._definitions_dir):
            raise InvalidConversationSchemaError(
                f"Conversation definitions directory does not exist: {self._definitions_dir}"
            )

        for filename in os.listdir(self._definitions_dir):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(self._definitions_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)

                # Validate schema
                validated_model = ConversationDefinitionSchema.model_validate(raw_data)
                definition_dict = validated_model.model_dump()

                cid = definition_dict["id"]
                if cid in self._cache:
                    raise DuplicateConversationIdError(
                        f"Duplicate conversation ID '{cid}' found in file {filename}"
                    )

                self._cache[cid] = definition_dict

            except (json.JSONDecodeError, ValidationError) as e:
                raise InvalidConversationSchemaError(
                    f"Failed to load or validate conversation file '{filename}': {str(e)}"
                ) from e

    def get_by_id(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        definition = self._cache.get(conversation_id)
        if not definition:
            raise ConversationTypeNotFoundError(
                f"Conversation definition with id '{conversation_id}' not found."
            )
        return definition

    def list_available(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": data["id"],
                "name": data.get("name", data["id"]),
                "description": data.get("description", ""),
                "version": data.get("version", "1.0"),
            }
            for data in self._cache.values()
        ]

    def exists(self, conversation_id: str) -> bool:
        return conversation_id in self._cache
