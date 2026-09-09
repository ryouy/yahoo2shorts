from fastapi import APIRouter, HTTPException

from ..storage.repository import repo

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(404, "Jobが見つかりません。")
    return job


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(404, "Jobが見つかりません。")
    if job["status"] not in ("queued", "running"):
        raise HTTPException(409, "このJobは処理中ではないためキャンセルできません。")
    repo.update_job(job_id, status="cancelling", log="キャンセルを要求しました。")
    return repo.get_job(job_id)

