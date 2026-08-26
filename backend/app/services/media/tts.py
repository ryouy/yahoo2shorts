from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path

import edge_tts

from ...storage.files import clean_text
from ...core.platform_utils import find_executable


def run_checked(command: list[str], label: str) -> str:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"{label} failed (exit={result.returncode})\n{result.stdout[-5000:]}")
    return result.stdout


def require_binary(name: str) -> str:
    value = find_executable(name)
    if not value:
        install = " macOSでは `brew install ffmpeg` を実行し、アプリを再起動してください。" if name in {"ffmpeg", "ffprobe"} else ""
        raise RuntimeError(f"{name} が見つかりません。{install}")
    return value


def media_duration(path: Path) -> float:
    output = run_checked([require_binary("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)], "ffprobe")
    return float(output.strip())


def synthesize_voice(text: str, output: Path, *, voice: str, rate: str) -> None:
    value = clean_text(text)
    if not value:
        raise ValueError("TTS対象テキストが空です。")
    output.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(3):
        try:
            communicate = edge_tts.Communicate(value, voice, rate=rate)
            if hasattr(communicate, "save_sync"):
                communicate.save_sync(str(output))
            else:
                asyncio.run(communicate.save(str(output)))
            if not output.exists() or output.stat().st_size < 100:
                raise RuntimeError("TTS出力が空です。")
            return
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"音声生成に失敗しました: {last_error}") from last_error
