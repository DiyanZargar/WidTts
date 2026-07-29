from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from app.entrypoints.websocket.conversation_handler import (
    router as ws_router,
    get_conversation_repository,
)
from app.entrypoints.http.health import router as health_router
from app.shared.database.init_db import init_db
from app.shared.logging.logger import logger

app = FastAPI(title="Conversational Widget Platform Backend")

static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

# API routes (registered first → take priority)
app.include_router(health_router)
app.include_router(ws_router)

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
    if path.startswith("ws/") or path.startswith("health"):
        raise HTTPException(status_code=404, detail="Not Found")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Not Found")


@app.on_event("startup")
async def on_startup():
    logger.info("Initializing database migrations...")
    init_db()

    logger.info("Loading and validating conversation definitions...")
    repo = get_conversation_repository()
    available = repo.list_available()
    logger.info(f"Successfully loaded {len(available)} conversation packs: {[p['id'] for p in available]}")
