from __future__ import annotations

import importlib.metadata
import sys
import tempfile
from pathlib import Path

import requests

from .config import RUNS_DIR
from .platform_utils import find_executable
from .security import secret_store
from ..services.media.fonts import find_japanese_font
from ..services.media.tts import synthesize_voice
from ..services.yahoo.browser import find_chrome_binary


def _check(name: str, callback, install: str) -> dict:
    try:
        detail = callback()
        return {"name": name, "ok": True, "detail": str(detail), "install": ""}
    except Exception as exc:
        return {"name": name, "ok": False, "detail": str(exc), "install": install}


def run_preflight(*, check_yahoo: bool = False, check_tts: bool = False) -> list[dict]:
    from ..storage.database import db

    output_dir = Path(str(db.settings().get("output_folder") or RUNS_DIR)).expanduser()
    checks = [
        {"name": "Python", "ok": sys.version_info >= (3, 11), "detail": sys.version.split()[0], "install": "Python 3.11以上をインストールしてください。"},
        _check("Chrome", find_chrome_binary, "Google Chrome または Chromiumをインストールしてください。"),
        _check("ffmpeg", lambda: find_executable("ffmpeg") or (_ for _ in ()).throw(RuntimeError("未検出")), "アプリを再インストールしてください。"),
        _check("Japanese Font", lambda: find_japanese_font(), "Noto Sans JPをインストールしてください。"),
        _check("edge-tts", lambda: importlib.metadata.version("edge-tts"), "pip install edge-tts"),
        _check("Output Directory", lambda: output_dir if output_dir.exists() and output_dir.is_dir() else (_ for _ in ()).throw(RuntimeError(f"未作成: {output_dir}")), "設定した成果物フォルダの権限を確認してください。"),
        {"name": "OpenAI", "ok": bool(secret_store.get()), "detail": "登録済み" if secret_store.get() else "未登録", "install": "設定画面でAPIキーを登録してください。"},
    ]
    if check_yahoo:
        checks.append(_check("Yahoo News", lambda: requests.get("https://news.yahoo.co.jp/", timeout=10).status_code, "ネットワークまたは地域制限を確認してください。"))
    if check_tts:
        temp_dir = Path(tempfile.mkdtemp(prefix="yss-tts-"))
        checks.append(_check("Female Voice", lambda: _tts_check(temp_dir / "female.mp3", "ja-JP-NanamiNeural"), "edge-ttsのネットワーク接続を確認してください。"))
        checks.append(_check("Male Voice", lambda: _tts_check(temp_dir / "male.mp3", "ja-JP-KeitaNeural"), "edge-ttsのネットワーク接続を確認してください。"))
    return checks


def _tts_check(path: Path, voice: str) -> str:
    synthesize_voice("音声テストです。", path, voice=voice, rate="+22%")
    return f"{voice} ({path.stat().st_size} bytes)"
