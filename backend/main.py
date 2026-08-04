from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from app.entrypoints.websocket.conversation_handler import router as ws_router
from app.entrypoints.http.health import router as health_router
from app.entrypoints.http.admin import admin_router
from app.shared.database.init_db import init_db
from app.shared.database.db import close_pool
from app.shared.security.envelope_encryption import bootstrap_encryption_key
from app.shared.logging.logger import logger

app = FastAPI(title="widTTS Voice Platform")

static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

# API routes (registered first → take priority)
app.include_router(health_router)
app.include_router(ws_router)
app.include_router(admin_router)

# Static asset subdirectories
if os.path.isdir(static_dir):
    for subdir in ["assets", "models", "ort-wasm", "vad"]:
        d = os.path.join(static_dir, subdir)
        if os.path.isdir(d):
            app.mount(f"/{subdir}", StaticFiles(directory=d), name=subdir)

    # Individual root-level files needed by VAD at runtime
    for fname in ["silero_vad_v5.onnx", "vad.worklet.bundle.min.js", "worklet.js"]:
        fpath = os.path.join(static_dir, fname)
        if os.path.isfile(fpath):
            @app.get(f"/{fname}", include_in_schema=False)
            async def _serve_file(fp=fpath):
                return FileResponse(fp)

# SPA fallback — must be LAST so API routes win
@app.get("/", include_in_schema=False)
async def root():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/{path:path}", include_in_schema=False)
async def spa_fallback(path: str):
    if path.startswith("ws/") or path.startswith("health") or path.startswith("admin/api"):
        raise HTTPException(status_code=404, detail="Not Found")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not Found")


@app.on_event("startup")
async def on_startup():
    logger.info("[STARTUP] Initializing PostgreSQL database...")
    await init_db()

    logger.info("[STARTUP] Bootstrapping encryption key...")
    key_version = await bootstrap_encryption_key()
    logger.info(f"[STARTUP] Active encryption key_version={key_version}")

    logger.info("[STARTUP] widTTS Voice Platform ready.")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("[SHUTDOWN] Closing database pool...")
    await close_pool()
    logger.info("[SHUTDOWN] Shutdown complete.")
