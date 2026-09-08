from __future__ import annotations

import json
import math
import shutil
import wave
from pathlib import Path

import numpy as np

from ...storage.files import safe_title_stem, save_json
from .renderer import render_frame, render_thumbnail
from .tts import media_duration, require_binary, run_checked, synthesize_voice


def _voice_pool(settings: dict) -> list[str]:
    """Configured voice pool with a fallback for projects created before v6 voices."""
    voices = [str(settings.get(f"voice_{index}") or "").strip() for index in range(1, 7)]
    voices = list(dict.fromkeys(voice for voice in voices if voice))
    return voices or [settings["voice_female"], settings["voice_male"]]


def _voice(index: int, post: dict, assigned: dict[int, str], settings: dict) -> str:
    pool = _voice_pool(settings)
    default = pool[(index - 1) % len(pool)]
    parent = assigned.get(post.get("reply_to"))
    if parent:
        for offset in range(1, len(pool) + 1):
            candidate = pool[(index - 1 + offset) % len(pool)]
            if candidate != parent:
                return candidate
    return default


def prepare_tts(script: dict, audio_dir: Path, settings: dict, progress=None) -> tuple[dict, dict, list[str]]:
    working = json.loads(json.dumps(script, ensure_ascii=False))
    removed: list[str] = []
    voices = _voice_pool(settings)
    intro_path = audio_dir / "intro.mp3"
    synthesize_voice(working["intro"]["narration"], intro_path, voice=voices[0], rate=settings["voice_rate"])
    intro = {"path": intro_path, "duration": media_duration(intro_path) + .05}
    assigned, posts = {}, []
    total_posts = len(working["posts"])
    for index, post in enumerate(working["posts"], 1):
        if progress:
            progress(12 + int(25 * index / max(1, total_posts)), f"TTS生成 {index}/{total_posts}")
        voice = _voice(index, post, assigned, settings)
        path = audio_dir / f"post_{index:03d}.mp3"
        voice = synthesize_voice(post["text"], path, voice=voice, rate=settings["voice_rate"])
        assigned[index] = voice
        posts.append({"original_index": index, "post": post, "path": path, "voice": voice, "duration": media_duration(path) + .05})
    outro_path = audio_dir / "outro.mp3"
    synthesize_voice(working["outro"]["narration"], outro_path, voice=voices[1 % len(voices)], rate=settings["voice_rate"])
    outro = {"path": outro_path, "duration": media_duration(outro_path) + .05}
    total = lambda items: intro["duration"] + sum(item["duration"] for item in items) + outro["duration"]
    while total(posts) > settings["target_video_seconds"] and len(posts) > 4:
        referenced = {item["post"].get("reply_to") for item in posts if item["post"].get("reply_to")}
        removable = [item for item in posts if item["original_index"] not in referenced] or posts
        victim = min(removable, key=lambda item: (int(item["post"].get("importance", 3)), -item["original_index"]))
        removed.append(victim["post"]["text"]); posts.remove(victim)
    duration = total(posts)
    if duration > settings["hard_max_video_seconds"]:
        raise RuntimeError(f"4件まで削減しても{duration:.1f}秒です。原稿を短くしてください。")
    old_to_new = {item["original_index"]: index for index, item in enumerate(posts, 1)}
    final_posts, meta_posts = [], []
    for index, item in enumerate(posts, 1):
        post = dict(item["post"])
        post["reply_to"] = old_to_new.get(post.get("reply_to"))
        post["voice"] = item["voice"]
        final_posts.append(post)
        meta_posts.append({"index": index, "path": item["path"], "duration": item["duration"]})
    working["posts"] = final_posts
    working["actual_tts_seconds"] = round(duration, 2)
    return working, {"intro": intro, "posts": meta_posts, "outro": outro}, removed


def _static_clip(image: Path, audio: Path, output: Path, settings: dict) -> None:
    run_checked([
        require_binary("ffmpeg"), "-y", "-loop", "1", "-i", str(image), "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", str(settings["fps"]),
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(output),
    ], "ffmpeg static clip")


def _add_note(audio, rate, start, duration, frequency, volume):
    start_i, end_i = int(start * rate), min(len(audio), int((start + duration) * rate))
    if end_i <= start_i:
        return
    t = np.arange(end_i - start_i) / rate
    env = np.minimum(1, t / .02) * np.exp(-t * 2.2)
    audio[start_i:end_i] += np.sin(2 * np.pi * frequency * t) * env * volume


def generate_bgm(output: Path, bpm: int) -> None:
    rate, bars = 44100, 8
    beat = 60 / bpm; duration = bars * 4 * beat
    audio = np.zeros(int(duration * rate), dtype=np.float64)
    roots, arp = [261.63, 196, 220, 174.61], [1, 1.2599, 1.4983, 2, 1.4983, 2, 1.2599, 1.4983]
    for n in range(bars * 8):
        root = roots[(n // 8) % 4]
        _add_note(audio, rate, n * beat / 2, beat * .35, root * arp[n % 8] * 2, .055)
    for n in range(bars * 4):
        _add_note(audio, rate, n * beat, beat * .7, roots[(n // 4) % 4] / 2, .08)
    peak = np.max(np.abs(audio))
    if peak:
        audio = audio / peak * .72
    pcm = (audio * 32767).astype(np.int16)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as wav:
        wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(rate)
        wav.writeframes(np.column_stack([pcm, pcm]).reshape(-1).tobytes())


def build_video(script: dict, output_dir: Path, settings: dict, progress=None) -> dict:
    assets = output_dir / "video_assets"; audio_dir = output_dir / "audio"; frames = output_dir / "frames"
    for path in (assets, audio_dir, frames):
        path.mkdir(parents=True, exist_ok=True)
    if progress: progress(5, "原稿確認")
    fitted, audio, removed = prepare_tts(script, audio_dir, settings, progress)
    save_json(fitted, output_dir / "rendered_thread.json")
    for text in removed:
        if progress: progress(40, f"時間調整で削除: {text}")
    stem = safe_title_stem(fitted.get("title", output_dir.name), 20)
    thumbnail = output_dir / "thumbnail.png"
    article_image = output_dir / "article_image.jpg"
    render_thumbnail(fitted, thumbnail, settings, background_path=article_image)
    clips: list[Path] = []
    intro_image, intro_clip = frames / "intro.png", assets / "intro.mp4"
    render_frame(fitted, intro_image, settings, intro=True, background_path=article_image)
    _static_clip(intro_image, audio["intro"]["path"], intro_clip, settings); clips.append(intro_clip)
    # Track time for background switching (~10 seconds)
    elapsed_time = audio["intro"]["duration"]
    for index, _post in enumerate(fitted["posts"], 1):
        if progress: progress(42 + int(33 * index / len(fitted["posts"])), f"コメント映像生成 {index}/{len(fitted['posts'])}")
        image, clip = frames / f"post_{index:03d}.png", assets / f"post_{index:03d}.mp4"
        # Switch background every ~10 seconds for visual variety
        bg = article_image if int(elapsed_time) % 20 < 10 else None
        render_frame(fitted, image, settings, visible=index, background_path=bg)
        _static_clip(image, audio["posts"][index - 1]["path"], clip, settings); clips.append(clip)
        elapsed_time += audio["posts"][index - 1]["duration"]
    outro_image, outro_clip = frames / "outro.png", assets / "outro.mp4"
    bg = article_image if int(elapsed_time) % 20 < 10 else None
    render_frame(fitted, outro_image, settings, visible=len(fitted["posts"]), outro=True, background_path=bg)
    _static_clip(outro_image, audio["outro"]["path"], outro_clip, settings); clips.append(outro_clip)
    concat = assets / "concat.txt"
    concat.write_text("".join(f"file '{clip.as_posix()}'\n" for clip in clips), encoding="utf-8")
    no_bgm = assets / "without_bgm.mp4"
    if progress: progress(80, "動画結合")
    run_checked([require_binary("ffmpeg"), "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", "-movflags", "+faststart", str(no_bgm)], "ffmpeg concat")
    final = output_dir / "output.mp4"
    if settings["bgm_enabled"]:
        if progress: progress(90, "BGM合成")
        bgm = assets / "pop_bgm.wav"; generate_bgm(bgm, settings["bgm_bpm"])
        run_checked([
            require_binary("ffmpeg"), "-y", "-i", str(no_bgm), "-stream_loop", "-1", "-i", str(bgm),
            "-filter_complex", f"[0:a]volume=1[a0];[1:a]volume={settings['bgm_volume']}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(final),
        ], "ffmpeg BGM mix")
    else:
        shutil.copy2(no_bgm, final)
    duration = media_duration(final)
    if duration > settings["hard_max_video_seconds"]:
        raise RuntimeError(f"最終動画が上限を超えました（{duration:.2f}秒）。")
    if progress: progress(100, "生成完了")
    return {"video": final, "thumbnail": thumbnail, "duration": duration, "removed_posts": removed}
