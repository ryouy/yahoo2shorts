from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..core.config import RUNS_DIR
from ..storage.database import db
from ..storage.repository import repo

router = APIRouter(tags=["artifacts"])


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


def _safe_file(path: Path, media_type: str):
    resolved = path.resolve()
    configured = Path(str(db.settings().get("output_folder") or RUNS_DIR)).expanduser().resolve()
    allowed = RUNS_DIR.resolve() in resolved.parents or configured in resolved.parents
    if not resolved.is_file() or not allowed:
        raise HTTPException(404, "ファイルがありません。")
    return FileResponse(resolved, media_type=media_type, filename=resolved.name)
