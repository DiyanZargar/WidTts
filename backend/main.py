from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from app.entrypoints.http.health import router as health_router
from app.entrypoints.http.admin import admin_router
from app.entrypoints.http.realtime_token_routes import router as realtime_token_router
from app.entrypoints.http.public_bot_routes import router as public_bot_router
from app.shared.database.init_db import init_db
from app.shared.database.db import close_pool
from app.shared.security.envelope_encryption import bootstrap_encryption_key
from app.shared.logging.logger import logger
from app.shared.events.structured_events import app_startup, app_shutdown

app = FastAPI(title="widTTS Voice Platform")

static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

# API routes (registered first → take priority)
app.include_router(health_router)
app.include_router(admin_router)
app.include_router(realtime_token_router)
app.include_router(public_bot_router)

# Static asset subdirectories
if os.path.isdir(static_dir):
    for subdir in ["assets"]:
        d = os.path.join(static_dir, subdir)
        if os.path.isdir(d):
            app.mount(f"/{subdir}", StaticFiles(directory=d), name=subdir)

# SPA fallback — must be LAST so API routes win
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/{path:path}", include_in_schema=False)
async def spa_fallback(path: str):
    if path.startswith("health") or path.startswith("admin/api") or path.startswith("realtime/") or path.startswith("api/bot/"):
        raise HTTPException(status_code=404, detail="Not Found")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not Found")


@app.on_event("startup")
async def on_startup():
    errors = []

    # 1. Database connectivity
    logger.info("[STARTUP] Validating database connectivity...")
    try:
        await init_db()
        logger.info("[STARTUP] ✅ Database OK")
    except Exception as e:
        msg = f"Database connectivity failed: {e}"
        logger.error(f"[STARTUP] ❌ {msg}")
        errors.append(msg)

    # 2. Master encryption key
    key_version = 0
    logger.info("[STARTUP] Bootstrapping encryption key...")
    try:
        key_version = await bootstrap_encryption_key()
        if key_version < 1:
            errors.append("Encryption key bootstrap returned invalid version")
        else:
            logger.info("[STARTUP] ✅ Encryption key_version=%d", key_version)
    except Exception as e:
        msg = f"Encryption key bootstrap failed: {e}"
        logger.error(f"[STARTUP] ❌ {msg}")
        errors.append(msg)

    # 3. Seed default realtime config (must run AFTER encryption key bootstrap)
    logger.info("[STARTUP] Seeding default realtime config if needed...")
    try:
        from app.shared.database.init_db import seed_default_realtime_config
        await seed_default_realtime_config()
        logger.info("[STARTUP] ✅ Realtime config seed complete")
    except Exception as e:
        logger.warning("[STARTUP] ⚠️ Realtime config seed warning: %s (non-fatal)", e)

    # 4. Runtime configuration
    logger.info("[STARTUP] Checking runtime configuration...")
    try:
        from app.modules.voice.infrastructure.persistence.realtime_config_repository import RealtimeConfigRepository
        repo = RealtimeConfigRepository()
        config = await repo.get_active()
        if config:
            logger.info("[STARTUP] ✅ Runtime config found: server_url=%s", config.get("server_url", "?"))
        else:
            logger.warning("[STARTUP] ⚠️ No active runtime configuration — sessions will fail until configured via admin")
    except Exception as e:
        logger.warning("[STARTUP] ⚠️ Runtime config check failed: %s (non-fatal)", e)

    # 4. Active bot check
    logger.info("[STARTUP] Checking for active bot...")
    try:
        from app.modules.bot.infrastructure.persistence.postgres_bot_repository import PostgresBotRepository
        bot = await PostgresBotRepository().get_active()
        if bot:
            logger.info("[STARTUP] ✅ Active bot: %s (id=%s)", bot["name"], bot["id"])
        else:
            logger.warning("[STARTUP] ⚠️ No active bot configured — voice sessions require an active bot")
    except Exception as e:
        logger.warning("[STARTUP] ⚠️ Active bot check failed: %s (non-fatal)", e)

    # 5. Fail if critical validations failed
    if errors:
        for err in errors:
            logger.error("[STARTUP] FATAL: %s", err)
        raise RuntimeError(f"Startup validation failed: {'; '.join(errors)}")

    app_startup(version="1.0.0", db_ok=True, key_version=key_version)
    logger.info("[STARTUP] widTTS Voice Platform ready.")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("[SHUTDOWN] Closing database pool...")
    await close_pool()
    app_shutdown(reason="normal")
    logger.info("[SHUTDOWN] Shutdown complete.")
