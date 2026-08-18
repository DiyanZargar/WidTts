import json
import uuid
from typing import Optional, List, Dict, Any
from app.shared.database.db import get_connection
from app.modules.provider.domain.interfaces.speech_provider_repository_interface import SpeechProviderRepositoryInterface


class SpeechProviderRepository(SpeechProviderRepositoryInterface):
    """Generic repository for managing speech providers in the database."""

    async def create(self, provider: Dict[str, Any]) -> str:
        pid = provider.get("id", str(uuid.uuid4()))
        async with get_connection() as conn:
            await conn.execute(
                """INSERT INTO speech_providers
                   (id, name, provider_type, credentials_enc, key_version,
                    stt_model, stt_language, stt_extra, tts_model, tts_voice_id, tts_extra)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                pid, provider["name"], provider["provider_type"],
                json.dumps(provider.get("credentials_enc", {})),
                provider.get("key_version", 1),
                provider.get("stt_model", ""),
                provider.get("stt_language", "en"),
                json.dumps(provider.get("stt_extra", {})),
                provider.get("tts_model", ""),
                provider.get("tts_voice_id", ""),
                json.dumps(provider.get("tts_extra", {})),
            )
        return pid

    async def get_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        async with get_connection() as conn:
            row = await conn.fetchrow("SELECT * FROM speech_providers WHERE id = ?", provider_id)
            return self._row_to_dict(row) if row else None

    async def list_all(self) -> List[Dict[str, Any]]:
        async with get_connection() as conn:
            rows = await conn.fetch("SELECT * FROM speech_providers ORDER BY created_at DESC")
            return [self._row_to_dict(r) for r in rows]

    async def update(self, provider_id: str, updates: Dict[str, Any]) -> None:
        sets = []
        vals = []
        for key in ("name", "provider_type", "credentials_enc", "key_version",
                     "stt_model", "stt_language", "stt_extra",
                     "tts_model", "tts_voice_id", "tts_extra",
                     "last_test_status", "last_test_at"):
            if key in updates:
                val = updates[key]
                if key in ("credentials_enc", "stt_extra", "tts_extra"):
                    val = json.dumps(val)
                sets.append(f"{key} = ?")
                vals.append(val)
        if not sets:
            return
        sets.append("updated_at = datetime('now')")
        vals.append(provider_id)
        sql = f"UPDATE speech_providers SET {', '.join(sets)} WHERE id = ?"
        async with get_connection() as conn:
            await conn.execute(sql, *vals)

    async def delete(self, provider_id: str) -> None:
        async with get_connection() as conn:
            await conn.execute("DELETE FROM speech_providers WHERE id = ?", provider_id)

    @staticmethod
    def _row_to_dict(row) -> Dict[str, Any]:
        d = dict(row)
        for key in ("credentials_enc", "stt_extra", "tts_extra"):
            if key in d and isinstance(d[key], str):
                d[key] = json.loads(d[key])
        return d
