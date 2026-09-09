from __future__ import annotations

import csv
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..models.schemas import ScriptSave
from ..services.jobs import job_runner
from ..services.script.generator import generate_script
from ..services.script.validator import estimate_script_seconds, validate_script
from ..storage.database import db
from ..storage.files import load_json, save_json
from ..storage.repository import repo

router = APIRouter(tags=["articles"])


def _article(article_id: int) -> dict:
    article = repo.get_article(article_id)
    if not article:
        raise HTTPException(404, "記事が見つかりません。")
    return article


@router.get("/articles/{article_id}")
def get_article(article_id: int):
    return _article(article_id)


@router.put("/articles/{article_id}/script")
def save_script(article_id: int, payload: ScriptSave):
    article = _article(article_id)
    video_mode = (repo.get_project(article["project_id"]) or {}).get("video_mode", "normal")
    content = payload.script.model_dump()
    try:
        validate_script(content, set(), db.settings(), editor=True, video_mode=video_mode)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    content["title"], content["source"], content["url"] = article["title"], article["source"], article["url"]
    content["estimated_seconds"] = estimate_script_seconds(content, video_mode=video_mode)
    repo.save_script(article_id, content, approved=False)
    if article.get("draft_path"):
        save_json(content, Path(article["draft_path"]))
    repo.update_article(article_id, status="waiting_script_approval", error=None)
    return repo.get_article(article_id)


@router.post("/articles/{article_id}/script/regenerate")
def regenerate_script(article_id: int):
    article = _article(article_id)
    if not article.get("article_path") or not article.get("comments_path"):
        raise HTTPException(409, "記事本文またはコメントがありません。")
    source_article = load_json(Path(article["article_path"]))
    with Path(article["comments_path"]).open(encoding="utf-8-sig") as stream:
        comments = list(csv.DictReader(stream))
    video_mode = (repo.get_project(article["project_id"]) or {}).get("video_mode", "normal")
    try:
        content = generate_script(source_article, comments, db.settings(), video_mode=video_mode)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    repo.save_script(article_id, content, approved=False)
    if article.get("draft_path"):
        save_json(content, Path(article["draft_path"]))
    repo.update_article(article_id, status="waiting_script_approval", error=None)
    return repo.get_article(article_id)


@router.post("/articles/{article_id}/script/approve")
def approve_script(article_id: int):
    article = _article(article_id)
    if not article.get("script"):
        raise HTTPException(409, "原稿がありません。")
    content = article["script"]["content"]
    try:
        validate_script(content, set(), db.settings(), editor=True)
    except Exception as exc:
        raise HTTPException(422, str(exc)) from exc
    if not article.get("output_dir"):
        raise HTTPException(409, "原稿の出力先がありません。原稿を再生成してください。")
    approved_path = Path(article["output_dir"]) / "approved_thread.json"
    save_json(content, approved_path)
    repo.save_script(article_id, content, approved=True)
    repo.update_article(article_id, status="ready_for_video", approved_path=str(approved_path))
    project = repo.get_project(article["project_id"])
    if project and all((not item["selected"]) or item["status"] in {"ready_for_video", "completed", "error"} for item in project["articles"]):
        repo.update_project(article["project_id"], status="ready_for_video")
    return repo.get_article(article_id)


@router.put("/articles/{article_id}/bgm")
def set_bgm(article_id: int, payload: dict):
    _article(article_id)
    track = (payload.get("bgm_track") or "").strip() or None
    repo.update_article(article_id, bgm_track=track)
    return repo.get_article(article_id)


@router.post("/articles/{article_id}/generate-video", status_code=202)
def generate_video(article_id: int):
    try:
        return job_runner.start_video(article_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/articles/{article_id}/retry", status_code=202)
def retry_article(article_id: int):
    article = _article(article_id)
    try:
        return job_runner.start_scripts(article["project_id"], [article_id])
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
