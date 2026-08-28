from __future__ import annotations

import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from .database import db, utc_now

JST = ZoneInfo("Asia/Tokyo")


class Repository:
    def create_project(self, mode: str, request_text: str, article_count: int) -> dict:
        base = datetime.now(JST).strftime("%Y%m%d_%H%M%S")
        project_id = base
        suffix = 2
        while db.fetchone("SELECT id FROM projects WHERE id=?", (project_id,)):
            project_id = f"{base}_{suffix}"
            suffix += 1
        now = utc_now()
        db.execute(
            "INSERT INTO projects(id,status,request_mode,request_text,article_count,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (project_id, "created", mode, request_text, article_count, now, now),
        )
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict | None:
        project = db.fetchone("SELECT * FROM projects WHERE id=?", (project_id,))
        if not project:
            return None
        project["articles"] = self.list_articles(project_id)
        project["jobs"] = db.fetchall(
            "SELECT * FROM jobs WHERE project_id=? ORDER BY created_at DESC LIMIT 15", (project_id,)
        )
        for job in project["jobs"]:
            job["logs"] = json.loads(job.pop("logs_json") or "[]")
        return project

    def list_projects(self) -> list[dict]:
        rows = db.fetchall(
            "SELECT p.*, COUNT(a.id) article_total, "
            "SUM(CASE WHEN a.status='completed' THEN 1 ELSE 0 END) success_count, "
            "SUM(CASE WHEN a.status='error' THEN 1 ELSE 0 END) error_count "
            "FROM projects p LEFT JOIN articles a ON a.project_id=p.id "
            "GROUP BY p.id ORDER BY p.created_at DESC"
        )
        return rows

    def delete_project(self, project_id: str) -> bool:
        """Delete a project and its related rows, but never interrupt an active job."""
        with db.transaction() as connection:
            if connection.execute("SELECT 1 FROM jobs WHERE project_id=? AND status IN ('queued','running') LIMIT 1", (project_id,)).fetchone():
                raise ValueError("処理中のプロジェクトは削除できません。")
            result = connection.execute("DELETE FROM projects WHERE id=?", (project_id,))
            return result.rowcount > 0

    def update_project(self, project_id: str, **values) -> None:
        if not values:
            return
        values["updated_at"] = utc_now()
        assignments = ",".join(f"{key}=?" for key in values)
        db.execute(f"UPDATE projects SET {assignments} WHERE id=?", (*values.values(), project_id))

    def replace_candidates(self, project_id: str, candidates: list[dict]) -> list[dict]:
        now = utc_now()
        with db.transaction() as connection:
            connection.execute("DELETE FROM articles WHERE project_id=? AND status='candidate'", (project_id,))
            for item in candidates:
                connection.execute(
                    "INSERT INTO articles(project_id,url,title,source,published_at,age_hours,comment_count,"
                    "ai_score,comment_score,freshness_score,combined_score,reason,discovery_source,selected,status,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(project_id,url) DO UPDATE SET title=excluded.title, source=excluded.source, "
                    "published_at=excluded.published_at, age_hours=excluded.age_hours, comment_count=excluded.comment_count, "
                    "ai_score=excluded.ai_score, comment_score=excluded.comment_score, freshness_score=excluded.freshness_score, "
                    "combined_score=excluded.combined_score, reason=excluded.reason, discovery_source=excluded.discovery_source, updated_at=excluded.updated_at",
                    (
                        project_id, item["url"], item.get("title", ""), item.get("source", ""),
                        item.get("published_at"), item.get("age_hours"), item.get("comment_count", 0),
                        item.get("ai_score", 0), item.get("comment_score", 0), item.get("freshness_score", 0),
                        item.get("combined_score", 0), item.get("reason", ""), item.get("discovery_source", ""),
                        0, "candidate", now, now,
                    ),
                )
        return self.list_articles(project_id)

    def list_articles(self, project_id: str) -> list[dict]:
        articles = db.fetchall("SELECT * FROM articles WHERE project_id=? ORDER BY combined_score DESC,id", (project_id,))
        scripts = {
            row["article_id"]: row
            for row in db.fetchall(
                "SELECT * FROM scripts WHERE article_id IN (SELECT id FROM articles WHERE project_id=?)",
                (project_id,),
            )
        }
        for article in articles:
            script = scripts.get(article["id"])
            if script:
                script["content"] = json.loads(script.pop("content_json"))
            article["script"] = script
        return articles

    def get_article(self, article_id: int) -> dict | None:
        article = db.fetchone("SELECT * FROM articles WHERE id=?", (article_id,))
        if article:
            script = db.fetchone("SELECT * FROM scripts WHERE article_id=?", (article_id,))
            if script:
                script["content"] = json.loads(script.pop("content_json"))
            article["script"] = script
        return article

    def approve_articles(self, project_id: str, article_ids: list[int]) -> None:
        now = utc_now()
        with db.transaction() as connection:
            connection.execute("UPDATE articles SET selected=0,updated_at=? WHERE project_id=?", (now, project_id))
            if article_ids:
                placeholders = ",".join("?" for _ in article_ids)
                connection.execute(
                    f"UPDATE articles SET selected=1,status='approved',updated_at=? WHERE project_id=? AND id IN ({placeholders})",
                    (now, project_id, *article_ids),
                )
        self.update_project(project_id, status="fetching_content")

    def update_article(self, article_id: int, **values) -> None:
        if not values:
            return
        values["updated_at"] = utc_now()
        assignments = ",".join(f"{key}=?" for key in values)
        db.execute(f"UPDATE articles SET {assignments} WHERE id=?", (*values.values(), article_id))

    def save_script(self, article_id: int, content: dict, approved: bool = False) -> None:
        estimated = float(content.get("estimated_seconds") or 0)
        db.execute(
            "INSERT INTO scripts(article_id,content_json,approved,estimated_seconds,updated_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(article_id) DO UPDATE SET content_json=excluded.content_json, approved=excluded.approved, "
            "estimated_seconds=excluded.estimated_seconds,updated_at=excluded.updated_at",
            (article_id, json.dumps(content, ensure_ascii=False), int(approved), estimated, utc_now()),
        )

    def create_job(self, kind: str, project_id: str | None, article_id: int | None = None) -> dict:
        job_id = uuid.uuid4().hex
        now = utc_now()
        # This guard lives in the same write transaction as insertion.  The
        # runner also checks earlier for a friendly error, but this closes the
        # check-then-create race from simultaneous API requests.
        with db.transaction() as connection:
            if project_id and connection.execute(
                "SELECT 1 FROM jobs WHERE project_id=? AND status IN ('queued','running') LIMIT 1",
                (project_id,),
            ).fetchone():
                raise ValueError("このプロジェクトでは別の処理が進行中です。")
            connection.execute(
                "INSERT INTO jobs(id,project_id,article_id,kind,status,progress,stage,logs_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (job_id, project_id, article_id, kind, "queued", 0, "待機中", "[]", now, now),
            )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict | None:
        job = db.fetchone("SELECT * FROM jobs WHERE id=?", (job_id,))
        if job:
            job["logs"] = json.loads(job.pop("logs_json") or "[]")
        return job

    def get_active_job(self, project_id: str) -> dict | None:
        """Return the newest queued/running job for a project, if one exists.

        Jobs mutate the same article and project records, so allowing them to run
        concurrently would make their final status depend on timing.
        """
        job = db.fetchone(
            "SELECT * FROM jobs WHERE project_id=? AND status IN ('queued','running') "
            "ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        )
        if job:
            job["logs"] = json.loads(job.pop("logs_json") or "[]")
        return job

    def update_job(self, job_id: str, *, progress: int | None = None, stage: str | None = None,
                   status: str | None = None, error: str | None = None, log: str | None = None) -> None:
        job = self.get_job(job_id)
        if not job:
            return
        logs = job.get("logs", [])
        if log:
            logs.append({"at": utc_now(), "message": log})
            logs = logs[-300:]
        values = {
            "progress": job["progress"] if progress is None else max(0, min(100, progress)),
            "stage": stage if stage is not None else job["stage"],
            "status": status if status is not None else job["status"],
            "error": error,
            "logs_json": json.dumps(logs, ensure_ascii=False),
            "updated_at": utc_now(),
        }
        db.execute(
            "UPDATE jobs SET progress=?,stage=?,status=?,error=?,logs_json=?,updated_at=? WHERE id=?",
            (*values.values(), job_id),
        )


repo = Repository()
