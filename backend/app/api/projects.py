from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..core.config import RUNS_DIR
from ..core.platform_utils import open_path
from ..models.schemas import ArticleApproval, DiscoveryRequest, ProjectCreate
from ..services.jobs import job_runner
from ..storage.files import create_project_zip, save_json
from ..storage.database import db
from ..storage.repository import repo

router = APIRouter(tags=["projects"])


def _run_dir(project_id: str) -> Path:
    root = Path(str(db.settings().get("output_folder") or RUNS_DIR)).expanduser().resolve()
    return root / project_id


@router.get("/projects")
def list_projects():
    return {"projects": repo.list_projects()}


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate):
    request_text = "\n".join(payload.urls) if payload.mode == "url" else payload.request_text
    project = repo.create_project(payload.mode, request_text, payload.article_count)
    _run_dir(project["id"]).mkdir(parents=True, exist_ok=True)
    return project


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    project = repo.get_project(project_id)
    if not project:
        raise HTTPException(404, "Projectが見つかりません。")
    return project


@router.post("/projects/{project_id}/discover", status_code=202)
def discover(project_id: str, payload: DiscoveryRequest):
    if not repo.get_project(project_id):
        raise HTTPException(404, "Projectが見つかりません。")
    if payload.mode == "url" and not payload.urls:
        raise HTTPException(422, "記事URLを1件以上入力してください。")
    if payload.mode != "url" and not payload.request_text.strip():
        raise HTTPException(422, "記事条件を入力してください。")
    return job_runner.start_discovery(project_id, payload.model_dump())


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


@router.post("/projects/{project_id}/generate-scripts", status_code=202)
def generate_scripts(project_id: str):
    if not any(item["selected"] for item in repo.list_articles(project_id)):
        raise HTTPException(409, "記事を承認してください。")
    return job_runner.start_scripts(project_id)


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
