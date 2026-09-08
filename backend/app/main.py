from __future__ import annotations

import logging
import os
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import articles, artifacts, jobs, projects, settings
from .core.config import ROOT_DIR
from .core.exceptions import AppError
from .storage.database import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.initialize()
    yield


app = FastAPI(title="Yahoo Shorts Studio", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def app_error_handler(_request: Request, exc: AppError):
    return JSONResponse(status_code=400, content={"detail": str(exc), "code": exc.code})


@app.get("/api/health")
def health():
    return {"ok": True, "app": "Yahoo Shorts Studio"}


@app.post("/api/restart")
def restart_server(request: Request):
    """Restart the backend server (localhost only)"""
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "localhost"):
        return JSONResponse(status_code=403, content={"detail": "Forbidden"})

    # Schedule restart in background
    def do_restart():
        import time
        time.sleep(1)
        os.execv(sys.executable, [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"])

    subprocess.Popen([sys.executable, "-c", "import time, os, sys; time.sleep(1); os.execv(sys.executable, [sys.executable, '-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', '8000'])"])
    return {"ok": True, "message": "Restarting server..."}


for router in (settings.router, projects.router, articles.router, jobs.router, artifacts.router):
    app.include_router(router, prefix="/api")

frontend_dist = Path(os.getenv("YSS_FRONTEND_DIST", ROOT_DIR / "frontend" / "dist"))
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
