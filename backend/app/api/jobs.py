from fastapi import APIRouter, HTTPException

from ..storage.repository import repo

router = APIRouter(tags=["jobs"])


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = repo.get_job(job_id)
    if not job:
        raise HTTPException(404, "Jobが見つかりません。")
    return job

