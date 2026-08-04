# CLEANUP REPORT — widTTS Repository Audit

**Date**: 2026-08-04  
**Scope**: Full scan of `backend/app/`, `backend/tests/`, `frontend/src/`

---

## 1. Empty Module Directories (DELETED)

Six module directories existed with Clean Architecture scaffolding (`application/`, `domain/`, `infrastructure/` subdirs) but contained **zero Python files** and had **zero inbound imports** from any production code.

| Directory | Status |
|---|---|
| `backend/app/modules/context/` | ✅ DELETED |
| `backend/app/modules/coordination/` | ✅ DELETED |
| `backend/app/modules/events/` | ✅ DELETED |
| `backend/app/modules/policy/` | ✅ DELETED |
| `backend/app/modules/routing/` | ✅ DELETED |
| `backend/app/modules/runtime/` | ✅ DELETED |

**Impact**: None. No code referenced these directories.

---

## 2. Empty Shared Constants Directory (KEPT)

`backend/app/shared/constants/__init__.py` exists but is empty. Zero inbound imports.  
**Decision**: Keep — will be populated with new platform constants during Phase 5/6.

---

## 3. Empty Entity Directory

`backend/app/modules/conversation/domain/entities/__init__.py` — empty `__init__.py`, no entity files.  
**Decision**: Keep — the conversation bounded context uses `TurnContext` and `ConversationFSM` in the `models/` dir instead. Not a bug, just a structural choice.

---

## 4. Duplicate Test File (RESOLVED)

| File | Status |
|---|---|
| `backend/tests/session/test_runtime_state_manager.py` | ✅ DELETED (duplicate) |
| `backend/tests/modules/session/test_runtime_state_manager.py` | ✅ KEPT (canonical) |

Files differed only in fixture names (`sm` vs `rsm`) and minor formatting. The `tests/modules/` version was the canonical, maintained copy.

---

## 5. Deepgram Leaks in Domain/Application Layers

**Result**: ✅ CLEAN. No Deepgram references found in any `modules/*/domain/` or `modules/*/application/` path. Deepgram is correctly isolated to `modules/voice/infrastructure/external/`.

---

## 6. Files Scheduled for Deletion in Phase 7

These files are currently in use but will be deleted once the Bot Prompt system (Phase 6) replaces them:

| File | Replacement |
|---|---|
| `json_conversation_repository.py` | Bot DB + system prompt |
| `conversation_schema.py` | Bot entity schema |
| `conversation_engine.py` | LLM prompt-driven flow |
| `validation_prompt.py` | Per-bot system prompt |
| `conversation_definitions/*.json` (4 files) | Bot DB records |
| `conversation_repository_interface.py` | Bot repository interface |
| `validate_response.py` | Simplified LLM adapter |

---

## 7. SQLite Files Scheduled for Replacement (Phase 2)

| File | Replacement |
|---|---|
| `shared/database/db.py` (SQLite) | asyncpg pool |
| `shared/database/migrations/runner.py` | Postgres migration runner |
| `sqlite_session_repository.py` | postgres_session_repository.py |
| `sqlite_message_repository.py` | postgres_message_repository.py |
| `sqlite_response_repository.py` | postgres_response_repository.py |
| `sqlite_interruption_repository.py` | postgres_interruption_repository.py |

---

## 8. Hardcoded Provider Config in `.env` (Phase 2)

All of these will be removed from `.env` and moved to DB-managed config:

- `DEEPGRAM_API_KEY`
- `DEEPGRAM_TTS_MODEL`
- `DEEPGRAM_STT_URL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `AI_VALIDATION_MODEL`
- `DATABASE_PATH`
- `CONVERSATION_DEFINITIONS_DIR`
- `MAX_RETRIES_PER_ITEM`

Only infrastructure secrets remain: `DATABASE_URL`, `MASTER_ENCRYPTION_KEY`, `APP_SECRET`, `PORT`.
