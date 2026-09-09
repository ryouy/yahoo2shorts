from __future__ import annotations

from pathlib import Path
import shutil

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..core.config import RUNS_DIR
from ..core.platform_utils import open_path
from ..models.schemas import ArticleApproval, DiscoveryRequest, ProjectCreate
from ..services.jobs import job_runner
from ..services.yahoo.article_fetcher import clean_direct_urls
from ..storage.files import create_project_zip, save_json
from ..storage.database import db
from ..storage.repository import repo

router = APIRouter(tags=["projects"])


def _run_dir(project_id: str) -> Path:
    root = Path(str(db.settings().get("output_folder") or RUNS_DIR)).expanduser().resolve()
    return root / project_id


def _validate_discovery_input(payload: ProjectCreate | DiscoveryRequest) -> dict:
    """Normalize input before persisting or queueing an expensive background job."""
    if payload.mode == "url":
        try:
            urls = clean_direct_urls(payload.urls)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if not urls:
            raise HTTPException(422, "記事URLを1件以上入力してください。")
        return {**payload.model_dump(), "urls": urls, "request_text": ""}
    request_text = payload.request_text.strip()
    if payload.mode == "request" and not request_text:
        raise HTTPException(422, "記事条件を入力してください。")
    return {**payload.model_dump(), "urls": [], "request_text": request_text}


@router.get("/projects")
def list_projects():
    return {"projects": repo.list_projects()}


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate):
    values = _validate_discovery_input(payload)
    request_text = "\n".join(values["urls"]) if values["mode"] == "url" else values["request_text"]
    project = repo.create_project(values["mode"], request_text, values["article_count"], values["video_mode"])
    _run_dir(project["id"]).mkdir(parents=True, exist_ok=True)
    return project


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(404, "Projectが見つかりません。")
    return project


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, force: bool = False):
    run_dir = _run_dir(project_id).resolve()
    root = Path(str(db.settings().get("output_folder") or RUNS_DIR)).expanduser().resolve()
    if run_dir.parent != root:
        raise HTTPException(400, "削除先が不正です。")
    try:
        deleted = repo.delete_project(project_id, force=force)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    if not deleted:
        raise HTTPException(404, "Projectが見つかりません。")
    if run_dir.exists():
        shutil.rmtree(run_dir)


@router.post("/projects/{project_id}/discover", status_code=202)
def discover(project_id: str, payload: DiscoveryRequest):
    if not repo.get_project(project_id):
        raise HTTPException(404, "Projectが見つかりません。")
    values = _validate_discovery_input(payload)
    try:
        return job_runner.start_discovery(project_id, values)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/projects/{project_id}/approve-articles")
def approve_articles(project_id: str, payload: ArticleApproval):
    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(404, "Projectが見つかりません。")
    available = {item["id"] for item in project["articles"]}
    if not set(payload.article_ids) <= available:
        raise HTTPException(422, "別Projectの記事が含まれています。")
    repo.approve_articles(project_id, payload.article_ids)
    selected = [item for item in repo.list_articles(project_id) if item["id"] in payload.article_ids]
    save_json({"articles": selected}, _run_dir(project_id) / "approved_articles.json")
    return {"articles": selected}


@router.post("/projects/{project_id}/full-pipeline", status_code=202)
def full_pipeline(project_id: str, payload: ArticleApproval):
    if not repo.get_project(project_id):
        raise HTTPException(404, "Projectが見つかりません。")
    try:
        return job_runner.start_full_pipeline(project_id, payload.article_ids)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/projects/{project_id}/generate-scripts", status_code=202)
def generate_scripts(project_id: str):
    if not repo.get_project(project_id):
        raise HTTPException(404, "Projectが見つかりません。")
    if not any(item["selected"] for item in repo.list_articles(project_id)):
        raise HTTPException(409, "記事を承認してください。")
    try:
        return job_runner.start_scripts(project_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/projects/{project_id}/approve-all-scripts")
def approve_all_scripts(project_id: str):
    from .articles import approve_script  # local import avoids a circular import at module load time

    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(404, "Projectが見つかりません。")
    pending = [item for item in project["articles"] if item.get("script") and not item["script"]["approved"]]
    if not pending:
        raise HTTPException(409, "承認待ちの原稿がありません。")
    approved, failed = [], []
    for item in pending:
        try:
            approve_script(item["id"])
            approved.append(item["id"])
        except HTTPException as exc:
            failed.append({"article_id": item["id"], "title": item.get("title", ""), "error": exc.detail})
    return {"approved": approved, "failed": failed}


@router.post("/projects/{project_id}/generate-videos", status_code=202)
def generate_videos(project_id: str):
    if not repo.get_project(project_id):
        raise HTTPException(404, "Projectが見つかりません。")
    try:
        return job_runner.start_video_batch(project_id)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/projects/{project_id}/zip")
def project_zip(project_id: str):
    run_dir = _run_dir(project_id).resolve()
    if not run_dir.exists():
        raise HTTPException(404, "成果物が見つかりません。")
    archive = create_project_zip(run_dir)
    return FileResponse(archive, filename=archive.name, media_type="application/zip")


@router.post("/projects/{project_id}/open-folder")
def open_project_folder(project_id: str):
    run_dir = _run_dir(project_id).resolve()
    if not run_dir.exists():
        raise HTTPException(404, "成果物フォルダが見つかりません。")
    open_path(run_dir)
    return {"ok": True}


@router.get("/history")
def get_history():
    """Get project history (alias for list_projects)"""
    return {"projects": repo.list_projects()}
