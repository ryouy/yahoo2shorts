from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from backend.app.services.yahoo.browser import find_chrome_binary

ROOT = Path(__file__).resolve().parent
HOST = os.getenv("YSS_HOST", "127.0.0.1")
PORT = int(os.getenv("YSS_PORT", "8000"))


def open_in_chrome(target: str) -> bool:
    """Open the UI in Chrome without falling back to the OS default browser."""
    try:
        chrome = find_chrome_binary()
    except RuntimeError as exc:
        print(f"Chromeを起動できませんでした: {exc}")
        print(f"手動で開いてください: {target}")
        return False
    subprocess.Popen(
        [chrome, "--new-tab", target],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def main() -> int:
    frontend_dist = ROOT / "frontend" / "dist"
    processes: list[subprocess.Popen] = []
    if not frontend_dist.exists():
        npm = shutil.which("npm")
        node_modules = ROOT / "frontend" / "node_modules"
        if npm and node_modules.exists():
            processes.append(subprocess.Popen([npm, "run", "dev"], cwd=ROOT / "frontend"))
            target = "http://127.0.0.1:5173"
        else:
            print("Frontend buildがありません。先に `cd frontend && npm install && npm run build` を実行してください。")
            target = f"http://{HOST}:{PORT}/docs"
    else:
        target = f"http://{HOST}:{PORT}"
    command = [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", HOST, "--port", str(PORT)]
    processes.append(subprocess.Popen(command, cwd=ROOT))

    def stop(*_args):
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    time.sleep(1.2)
    open_in_chrome(target)
    try:
        return processes[-1].wait()
    finally:
        stop()


if __name__ == "__main__":
    raise SystemExit(main())
