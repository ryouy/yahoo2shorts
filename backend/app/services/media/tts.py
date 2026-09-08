from __future__ import annotations

import asyncio
import re
import subprocess
import time
from pathlib import Path

import edge_tts

from ...storage.files import clean_text
from ...core.platform_utils import find_executable


# Two native Japanese voices plus multilingual voices verified to read Japanese.
# The service's available voice list changes over time, so this list also gives
# existing projects a safe fallback if a saved voice is retired.
FALLBACK_VOICES = (
    "ja-JP-NanamiNeural",
    "ja-JP-KeitaNeural",
    "en-US-AvaMultilingualNeural",
    "en-US-AndrewMultilingualNeural",
    "en-US-EmmaMultilingualNeural",
    "en-US-BrianMultilingualNeural",
)


def run_checked(command: list[str], label: str) -> str:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"{label} failed (exit={result.returncode})\n{result.stdout[-5000:]}")
    return result.stdout


def require_binary(name: str) -> str:
    value = find_executable(name)
    if not value:
        install = " アプリを再インストールしてください。" if name == "ffmpeg" else ""
        raise RuntimeError(f"{name} が見つかりません。{install}")
    return value


def media_duration(path: Path) -> float:
    # The bundled imageio-ffmpeg distribution provides ffmpeg but not ffprobe.
    # ffmpeg itself prints a reliable container duration without decoding media.
    result = subprocess.run(
        [require_binary("ffmpeg"), "-hide_banner", "-i", str(path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", result.stdout)
    if not match:
        raise RuntimeError(f"音声・動画の長さを取得できませんでした。\n{result.stdout[-1000:]}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def synthesize_voice(text: str, output: Path, *, voice: str, rate: str) -> str:
    value = clean_text(text)
    if not value:
        raise ValueError("TTS対象テキストが空です。")
    output.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    candidates = tuple(dict.fromkeys((voice, *FALLBACK_VOICES)))
    for candidate in candidates:
        for attempt in range(2):
            try:
                output.unlink(missing_ok=True)
                communicate = edge_tts.Communicate(value, candidate, rate=rate)
                if hasattr(communicate, "save_sync"):
                    communicate.save_sync(str(output))
                else:
                    asyncio.run(communicate.save(str(output)))
                if not output.exists() or output.stat().st_size < 100:
                    raise RuntimeError("TTS出力が空です。")
                return candidate
            except Exception as exc:
                last_error = exc
                output.unlink(missing_ok=True)
                if attempt == 0:
                    time.sleep(1)
    raise RuntimeError(f"音声生成に失敗しました。ネットワーク接続を確認してください: {last_error}") from last_error
