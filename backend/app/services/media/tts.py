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


def _silent_regions(path: Path, *, noise_db: int = -40, min_duration: float = 0.08) -> list[tuple[float, float]]:
    output = subprocess.run(
        [require_binary("ffmpeg"), "-i", str(path), "-af", f"silencedetect=noise={noise_db}dB:duration={min_duration}", "-f", "null", "-"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    ).stdout
    starts = [float(value) for value in re.findall(r"silence_start:\s*(-?[\d.]+)", output)]
    ends = [float(value) for value in re.findall(r"silence_end:\s*([\d.]+)", output)]
    return list(zip(starts, ends))


def _trim_silence(path: Path) -> None:
    """edge-tts pads each clip with leading/trailing silence. Concatenating many
    clips (intro/summary/posts/outro) stacks that padding into a noticeable gap
    between sections, so trim it down.

    Silence in the *middle* of a sentence (a natural pause at a comma/period)
    must never be touched — cutting it splices unrelated words together and
    sounds like cut-off or overlapping speech. So this only removes a region
    when it starts at (or before) time zero, or ends at (or after) the clip's
    end, i.e. genuine leading/trailing padding, each capped at 30% of the
    clip so a mis-detection can't gut most of the audio.
    """
    try:
        total = media_duration(path)
        regions = _silent_regions(path)
        if not regions:
            return
        start_cut = 0.0
        first_start, first_end = regions[0]
        if first_start <= 0.05:
            start_cut = min(first_end, total * 0.3)
        end_cut = 0.0
        last_start, last_end = regions[-1]
        if last_end >= total - 0.05:
            end_cut = min(total - last_start, total * 0.3)
        if start_cut <= 0 and end_cut <= 0:
            return
        new_duration = total - start_cut - end_cut
        if new_duration < total * 0.5:
            return
        trimmed = path.with_suffix(".trimmed.mp3")
        run_checked([
            require_binary("ffmpeg"), "-y", "-i", str(path),
            "-ss", f"{start_cut:.3f}", "-t", f"{new_duration:.3f}",
            "-c:a", "libmp3lame", "-b:a", "64k", str(trimmed),
        ], "ffmpeg trim silence")
        if trimmed.exists() and trimmed.stat().st_size > 100:
            trimmed.replace(path)
        else:
            trimmed.unlink(missing_ok=True)
    except Exception:
        pass


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
                _trim_silence(output)
                return candidate
            except Exception as exc:
                last_error = exc
                output.unlink(missing_ok=True)
                if attempt == 0:
                    time.sleep(1)
    raise RuntimeError(f"音声生成に失敗しました。ネットワーク接続を確認してください: {last_error}") from last_error
