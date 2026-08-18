import json
import uuid
from typing import Optional, List, Dict, Any
from app.shared.database.db import get_connection
from app.modules.provider.domain.interfaces.llm_provider_repository_interface import LLMProviderRepositoryInterface


class LLMProviderRepository(LLMProviderRepositoryInterface):
    """Generic repository for managing LLM providers in the database."""

    async def create(self, provider: Dict[str, Any]) -> str:
        pid = provider.get("id", str(uuid.uuid4()))
        async with get_connection() as conn:
            await conn.execute(
                """INSERT INTO llm_providers (id, name, provider_type, base_url, credentials_enc, key_version, is_default)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                pid, provider["name"], provider["provider_type"],
                provider.get("base_url", ""),
                json.dumps(provider.get("credentials_enc", {})),
                provider.get("key_version", 1),
                provider.get("is_default", False),
            )
        return pid

    async def get_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM llm_providers WHERE id = ?", provider_id)
            return self._row_to_dict(row) if row else None

    async def list_all(self) -> List[Dict[str, Any]]:
        async with get_connection() as conn:
            rows = await conn.fetch("SELECT * FROM llm_providers ORDER BY created_at DESC")
            return [self._row_to_dict(r) for r in rows]

    async def update(self, provider_id: str, updates: Dict[str, Any]) -> None:
        sets = []
        vals = []
        for key in ("name", "provider_type", "base_url", "credentials_enc", "key_version",
                     "available_models", "last_test_status", "last_test_at", "is_default"):
            if key in updates:
                val = updates[key]
                if key in ("credentials_enc", "available_models"):
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                vals.append(val)
        if not sets:
            return
        sets.append("updated_at = datetime('now')")
        vals.append(provider_id)
        sql = f"UPDATE llm_providers SET {', '.join(sets)} WHERE id = ?"
        async with get_connection() as conn:
            await conn.execute(sql, *vals)

    async def delete(self, provider_id: str) -> None:
        async with get_connection() as conn:
            await conn.execute("DELETE FROM llm_providers WHERE id = ?", provider_id)

    async def get_default(self) -> Optional[Dict[str, Any]]:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM llm_providers WHERE is_default = 1")
            return self._row_to_dict(row) if row else None

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        d = dict(row)
        for key in ("credentials_enc", "available_models"):
            if key in d and isinstance(d[key], str):
                d[key] = json.loads(d[key])
        return d
