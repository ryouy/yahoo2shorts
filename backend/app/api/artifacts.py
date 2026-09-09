from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..core.config import BGM_DIR, RUNS_DIR
from ..services.media.renderer import render_thumbnail
from ..storage.database import db
from ..storage.repository import repo

router = APIRouter(tags=["artifacts"])

BGM_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}


@router.get("/bgm-tracks")
def list_bgm_tracks():
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    tracks = sorted(path.name for path in BGM_DIR.iterdir() if path.is_file() and path.suffix.lower() in BGM_EXTENSIONS)
    return {"tracks": tracks, "folder": str(BGM_DIR)}


@router.get("/bgm-tracks/{filename}")
def get_bgm_track(filename: str):
    path = (BGM_DIR / filename).resolve()
    if BGM_DIR.resolve() not in path.parents or not path.is_file():
        raise HTTPException(404, "音楽ファイルが見つかりません。")
    return FileResponse(path, media_type="audio/mpeg", filename=path.name)


@router.get("/articles/{article_id}/video")
def video(article_id: int):
    article = repo.get_article(article_id)
    if not article or not article.get("video_path"):
        raise HTTPException(404, "動画がありません。")
    return _safe_file(Path(article["video_path"]), "video/mp4")


@router.get("/articles/{article_id}/thumbnail")
def thumbnail(article_id: int):
    article = repo.get_article(article_id)
    if not article or not article.get("thumbnail_path"):
        raise HTTPException(404, "サムネイルがありません。")
    return _safe_file(Path(article["thumbnail_path"]), "image/png")


@router.post("/articles/{article_id}/preview-thumbnail")
def preview_thumbnail(article_id: int, script: dict):
    """Generate a temporary thumbnail preview from script data."""
    try:
        article = repo.get_article(article_id)
        settings = db.settings()
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        background_path = None
        if article and article.get("image_path"):
            background_path = Path(article["image_path"])
        render_thumbnail(script, tmp_path, settings, background_path=background_path)
        return FileResponse(tmp_path, media_type="image/png", filename="preview.png")
    except Exception as e:
        raise HTTPException(400, f"プレビュー生成に失敗: {str(e)}")


def _safe_file(path: Path, media_type: str):
    resolved = path.resolve()
    configured = Path(str(db.settings().get("output_folder") or RUNS_DIR)).expanduser().resolve()
    allowed = RUNS_DIR.resolve() in resolved.parents or configured in resolved.parents
    if not resolved.is_file() or not allowed:
        raise HTTPException(404, "ファイルがありません。")
    return FileResponse(resolved, media_type=media_type, filename=resolved.name)
