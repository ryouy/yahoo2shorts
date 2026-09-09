from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from ...core.config import BGM_DIR
from ...storage.files import safe_title_stem, save_json
from .renderer import paginate_summary_text, render_frame, render_summary_frame, render_thumbnail
from .tts import media_duration, require_binary, run_checked, synthesize_voice

BGM_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


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


def prepare_tts(script: dict, audio_dir: Path, settings: dict, progress=None, *, video_mode: str = "normal") -> tuple[dict, dict, list[str]]:
    working = json.loads(json.dumps(script, ensure_ascii=False))
    removed: list[str] = []
    voices = _voice_pool(settings)
    intro_path = audio_dir / "intro.mp3"
    synthesize_voice(working["intro"]["narration"], intro_path, voice=voices[0], rate=settings["voice_rate"])
    intro = {"path": intro_path, "duration": media_duration(intro_path) + .05}
    summary = None
    if video_mode == "gold":
        summary_path = audio_dir / "summary.mp3"
        summary_text = working["intro"].get("summary_narration") or working["intro"]["explainer"]
        synthesize_voice(summary_text, summary_path, voice=voices[0], rate=settings["voice_rate"])
        summary = {"path": summary_path, "duration": media_duration(summary_path) + .05}
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
    summary_seconds = summary["duration"] if summary else 0
    target_seconds = settings["gold_target_video_seconds"] if video_mode == "gold" else settings["target_video_seconds"]
    hard_max_seconds = settings["gold_hard_max_video_seconds"] if video_mode == "gold" else settings["hard_max_video_seconds"]
    min_posts = settings["gold_thread_post_min"] if video_mode == "gold" else settings["thread_post_min"]
    total = lambda items: intro["duration"] + summary_seconds + sum(item["duration"] for item in items) + outro["duration"]
    while total(posts) > target_seconds and len(posts) > min_posts:
        referenced = {item["post"].get("reply_to") for item in posts if item["post"].get("reply_to")}
        removable = [item for item in posts if item["original_index"] not in referenced] or posts
        victim = min(removable, key=lambda item: (int(item["post"].get("importance", 3)), -item["original_index"]))
        removed.append(victim["post"]["text"]); posts.remove(victim)
    duration = total(posts)
    if duration > hard_max_seconds:
        raise RuntimeError(f"コメントを{min_posts}件まで削減しても{duration:.1f}秒です。原稿を短くしてください。")
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
    return working, {"intro": intro, "summary": summary, "posts": meta_posts, "outro": outro}, removed


def _static_clip(image: Path, audio: Path, output: Path, settings: dict) -> None:
    run_checked([
        require_binary("ffmpeg"), "-y", "-loop", "1", "-i", str(image), "-i", str(audio),
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", str(settings["fps"]),
        "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(output),
    ], "ffmpeg static clip")


def _silent_clip(image: Path, duration: float, output: Path, settings: dict) -> None:
    run_checked([
        require_binary("ffmpeg"), "-y", "-loop", "1", "-i", str(image), "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", str(settings["fps"]),
        str(output),
    ], "ffmpeg silent clip")


def _build_summary_clip(script: dict, audio_path: Path, audio_duration: float, frames: Path, assets: Path, settings: dict, background_path: Path | None) -> Path:
    """Multiple mid-sized cards, timed to the narration by each page's share of the text."""
    text = script.get("intro", {}).get("summary_narration") or script["intro"]["explainer"]
    pages = paginate_summary_text(text)
    total_chars = sum(len(page) for page in pages) or 1
    remaining = audio_duration
    page_clips = []
    for index, page_text in enumerate(pages):
        if index == len(pages) - 1:
            duration = max(0.6, remaining)
        else:
            duration = max(0.6, audio_duration * len(page_text) / total_chars)
            remaining -= duration
        page_image = frames / f"summary_{index:02d}.png"
        render_summary_frame(script, page_text, index, len(pages), page_image, settings, background_path=background_path)
        page_clip = assets / f"summary_{index:02d}_silent.mp4"
        _silent_clip(page_image, duration, page_clip, settings)
        page_clips.append(page_clip)
    concat_file = assets / "summary_concat.txt"
    concat_file.write_text("".join(f"file '{clip.as_posix()}'\n" for clip in page_clips), encoding="utf-8")
    silent_all = assets / "summary_silent.mp4"
    run_checked([require_binary("ffmpeg"), "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file), "-c", "copy", str(silent_all)], "ffmpeg summary concat")
    summary_clip = assets / "summary.mp4"
    run_checked([
        require_binary("ffmpeg"), "-y", "-i", str(silent_all), "-i", str(audio_path),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(summary_clip),
    ], "ffmpeg summary mux")
    return summary_clip



def build_video(script: dict, output_dir: Path, settings: dict, progress=None, *, video_mode: str = "normal", bgm_track: str | None = None) -> dict:
    assets = output_dir / "video_assets"; audio_dir = output_dir / "audio"; frames = output_dir / "frames"
    for path in (assets, audio_dir, frames):
        path.mkdir(parents=True, exist_ok=True)
    if progress: progress(5, "原稿確認")
    fitted, audio, removed = prepare_tts(script, audio_dir, settings, progress, video_mode=video_mode)
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
    if video_mode == "gold" and audio.get("summary"):
        if progress: progress(40, "本文紹介映像生成")
        summary_clip = _build_summary_clip(
            fitted, audio["summary"]["path"], audio["summary"]["duration"], frames, assets, settings, article_image,
        )
        clips.append(summary_clip)
    # Use article image as background for all frames
    elapsed_time = audio["intro"]["duration"]
    for index, _post in enumerate(fitted["posts"], 1):
        if progress: progress(42 + int(33 * index / len(fitted["posts"])), f"コメント映像生成 {index}/{len(fitted['posts'])}")
        image, clip = frames / f"post_{index:03d}.png", assets / f"post_{index:03d}.mp4"
        render_frame(fitted, image, settings, visible=index, background_path=article_image)
        _static_clip(image, audio["posts"][index - 1]["path"], clip, settings); clips.append(clip)
        elapsed_time += audio["posts"][index - 1]["duration"]
    outro_image, outro_clip = frames / "outro.png", assets / "outro.mp4"
    render_frame(fitted, outro_image, settings, visible=len(fitted["posts"]), outro=True, background_path=article_image)
    _static_clip(outro_image, audio["outro"]["path"], outro_clip, settings); clips.append(outro_clip)
    concat = assets / "concat.txt"
    concat.write_text("".join(f"file '{clip.as_posix()}'\n" for clip in clips), encoding="utf-8")
    no_bgm = assets / "without_bgm.mp4"
    if progress: progress(80, "動画結合")
    run_checked([require_binary("ffmpeg"), "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", "-movflags", "+faststart", str(no_bgm)], "ffmpeg concat")
    final = output_dir / "output.mp4"
    bgm_path = None
    if bgm_track:
        candidate = (BGM_DIR / bgm_track).resolve()
        if BGM_DIR.resolve() in candidate.parents and candidate.is_file():
            bgm_path = candidate
    if not bgm_path:
        available = [
            path for path in BGM_DIR.iterdir() if path.is_file() and path.suffix.lower() in BGM_EXTENSIONS
        ] if BGM_DIR.exists() else []
        if available:
            bgm_path = random.choice(available)
    if bgm_path:
        if progress: progress(90, "BGM合成")
        run_checked([
            require_binary("ffmpeg"), "-y", "-i", str(no_bgm), "-stream_loop", "-1", "-i", str(bgm_path),
            "-filter_complex", f"[0:a]volume=1[a0];[1:a]volume={settings['bgm_volume']}[a1];[a0][a1]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(final),
        ], "ffmpeg BGM mix")
    else:
        shutil.copy2(no_bgm, final)
    duration = media_duration(final)
    hard_max_seconds = settings["gold_hard_max_video_seconds"] if video_mode == "gold" else settings["hard_max_video_seconds"]
    if duration > hard_max_seconds:
        raise RuntimeError(f"最終動画が上限を超えました（{duration:.2f}秒）。")
    if progress: progress(100, "生成完了")
    return {"video": final, "thumbnail": thumbnail, "duration": duration, "removed_posts": removed}
