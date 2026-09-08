"""Entry point bundled into the yc2ys desktop application's local server."""
from __future__ import annotations

import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    os.environ.setdefault("YSS_FRONTEND_DIST", str(Path(sys._MEIPASS) / "frontend_dist"))

import uvicorn

from backend.app.main import app


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.getenv("YSS_PORT", "18180")),
        log_level="warning",
    )
