from __future__ import annotations

import csv
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from ..core.config import RUNS_DIR
from ..storage.database import db
from ..storage.files import load_json, save_json, unique_article_dir
from ..storage.repository import repo
from .media.video_builder import build_video
from .script.generator import generate_script
from .yahoo.article_fetcher import fetch_yahoo_article
from .yahoo.comment_fetcher import fetch_yahoo_comments, parse_yahoo_datetime
from .yahoo.discovery import discover_articles


class JobRunner:
    def __init__(self) -> None:
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="yss-job")

    def _log_file(self, project_id: str, message: str) -> None:
        run_dir = self._run_dir(project_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        with (run_dir / "run.log").open("a", encoding="utf-8") as stream:
            stream.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")

    @staticmethod
    def _run_dir(project_id: str) -> Path:
        root = Path(str(db.settings().get("output_folder") or RUNS_DIR)).expanduser().resolve()
        return root / project_id

    def _update(self, job_id: str, project_id: str, progress: int, stage: str, log: str | None = None) -> None:
        repo.update_job(job_id, progress=progress, stage=stage, status="running", log=log or stage)
        self._log_file(project_id, log or stage)

    def start_discovery(self, project_id: str, payload: dict) -> dict:
        job = repo.create_job("article_discovery", project_id)
        repo.update_project(project_id, status="searching_articles", error=None)
        self.pool.submit(self._discover, job["id"], project_id, payload)
        return job

    def _discover(self, job_id: str, project_id: str, payload: dict) -> None:
        try:
            settings = db.settings()
            self._update(job_id, project_id, 2, "検索条件を準備")
            candidates = discover_articles(
                mode=payload["mode"], request_text=payload.get("request_text", ""), urls=payload.get("urls", []),
                article_count=payload.get("article_count", 3), settings=settings,
                progress=lambda stage, percent: self._update(job_id, project_id, percent, stage),
            )
            repo.replace_candidates(project_id, candidates)
            run_dir = self._run_dir(project_id)
            save_json({"articles": candidates}, run_dir / "article_proposals.json")
            with (run_dir / "article_proposals.csv").open("w", encoding="utf-8-sig", newline="") as stream:
                columns = ["url", "title", "source", "published_at", "comment_count", "ai_score", "comment_score", "freshness_score", "combined_score", "reason", "discovery_source"]
                writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore"); writer.writeheader(); writer.writerows(candidates)
            repo.update_project(project_id, status="waiting_article_approval", error=None)
            repo.update_job(job_id, progress=100, stage="候補の準備完了", status="completed", log=f"{len(candidates)}件の候補を作成")
        except Exception as exc:
            self._fail(job_id, project_id, exc)

    def start_scripts(self, project_id: str, article_ids: list[int] | None = None) -> dict:
        job = repo.create_job("script_generation", project_id, article_ids[0] if article_ids and len(article_ids) == 1 else None)
        repo.update_project(project_id, status="fetching_content", error=None)
        self.pool.submit(self._scripts, job["id"], project_id, article_ids)
        return job

    def _scripts(self, job_id: str, project_id: str, article_ids: list[int] | None = None) -> None:
        allowed = set(article_ids or [])
        articles = [item for item in repo.list_articles(project_id) if item["selected"] and (not allowed or item["id"] in allowed)]
        settings = db.settings(); failures = 0; records = []
        try:
            for position, selected in enumerate(articles, 1):
                base = int((position - 1) * 95 / max(1, len(articles)))
                span = max(1, int(95 / max(1, len(articles))))
                article_id = selected["id"]
                had_script = bool(selected.get("script"))
                try:
                    self._update(job_id, project_id, base + 2, f"記事{position}: 本文取得", selected["url"])
                    repo.update_article(article_id, status="fetching_content", error=None)
                    article = fetch_yahoo_article(selected["url"])
                    output_dir = unique_article_dir(self._run_dir(project_id), article["title"], article_id)
                    output_dir.mkdir(parents=True, exist_ok=True)
                    article_path = output_dir / "article.json"; save_json(article, article_path)
                    self._update(job_id, project_id, base + span // 3, f"記事{position}: コメント取得")
                    comments = fetch_yahoo_comments(
                        selected["url"], limit=settings["comment_limit"], include_replies=settings["include_replies"],
                        max_pages=settings["max_comment_pages"], published_at=parse_yahoo_datetime(article.get("published_at") or ""),
                        progress=lambda stage, _p, _t: self._log_file(project_id, stage),
                    )
                    comments_path = output_dir / "comments.csv"
                    with comments_path.open("w", encoding="utf-8-sig", newline="") as stream:
                        columns = ["comment_id", "comment_type", "parent_comment_id", "text", "posted_at", "empathy_count", "reply_count", "order_index"]
                        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore"); writer.writeheader(); writer.writerows(comments)
                    self._update(job_id, project_id, base + 2 * span // 3, f"記事{position}: AI原稿生成")
                    script = generate_script(article, comments, settings)
                    draft_path = output_dir / "draft_thread.json"; save_json(script, draft_path)
                    repo.save_script(article_id, script)
                    repo.update_article(
                        article_id, title=article["title"], source=article["source"], published_at=article.get("published_at"),
                        comment_count=len(comments), output_dir=str(output_dir), article_path=str(article_path), comments_path=str(comments_path),
                        draft_path=str(draft_path), status="waiting_script_approval", error=None,
                    )
                    records.append({"article_id": article_id, "title": article["title"], "output_dir": str(output_dir), "estimated_seconds": script["estimated_seconds"]})
                except Exception as exc:
                    failures += 1
                    repo.update_article(
                        article_id,
                        status="waiting_script_approval" if had_script else "error",
                        error=f"再生成失敗（既存原稿は保持）: {type(exc).__name__}: {exc}" if had_script else f"{type(exc).__name__}: {exc}",
                    )
                    self._log_file(project_id, f"記事{position}失敗: {traceback.format_exc()}")
            records_path = self._run_dir(project_id) / "draft_records.json"
            if records_path.exists() and article_ids:
                previous = load_json(records_path).get("records", [])
                replaced = {item["article_id"] for item in records}
                records = [item for item in previous if item.get("article_id") not in replaced] + records
            save_json({"records": records}, records_path)
            status = "partial_error" if failures else "waiting_script_approval"
            repo.update_project(project_id, status=status, error=f"{failures}件失敗" if failures else None)
            repo.update_job(job_id, progress=100, stage="原稿生成完了", status="completed", log=f"成功{len(records)}件 / 失敗{failures}件")
        except Exception as exc:
            self._fail(job_id, project_id, exc)

    def start_video(self, article_id: int) -> dict:
        article = repo.get_article(article_id)
        if not article:
            raise ValueError("記事が見つかりません。")
        if not article.get("script") or not article["script"]["approved"]:
            raise ValueError("承認済み原稿だけ動画生成できます。")
        job = repo.create_job("video_generation", article["project_id"], article_id)
        repo.update_article(article_id, status="generating_video", error=None)
        repo.update_project(article["project_id"], status="generating_video")
        self.pool.submit(self._video, job["id"], article_id)
        return job

    def start_video_batch(self, project_id: str) -> dict:
        # list_articles does not join scripts; resolve selected records first.
        eligible = [repo.get_article(item["id"]) for item in repo.list_articles(project_id) if item["selected"]]
        eligible = [item for item in eligible if item and item.get("script") and item["script"]["approved"]]
        if not eligible:
            raise ValueError("承認済み原稿がありません。")
        job = repo.create_job("video_batch", project_id)
        repo.update_project(project_id, status="generating_video", error=None)
        self.pool.submit(self._video_batch, job["id"], project_id, [item["id"] for item in eligible])
        return job

    def _video_batch(self, job_id: str, project_id: str, article_ids: list[int]) -> None:
        failures = 0
        for position, article_id in enumerate(article_ids, 1):
            article = repo.get_article(article_id)
            if not article or not article.get("script"):
                failures += 1
                continue
            base = int((position - 1) * 100 / len(article_ids))
            span = 100 / len(article_ids)
            try:
                repo.update_article(article_id, status="generating_video", error=None)
                result = build_video(
                    article["script"]["content"], Path(article["output_dir"]), db.settings(),
                    progress=lambda percent, stage, b=base, s=span, p=position: self._update(job_id, project_id, min(99, int(b + percent * s / 100)), f"記事{p}/{len(article_ids)}: {stage}"),
                )
                repo.update_article(article_id, status="completed", video_path=str(result["video"]), thumbnail_path=str(result["thumbnail"]), video_duration=result["duration"], error=None)
            except Exception as exc:
                failures += 1
                repo.update_article(article_id, status="error", error=f"{type(exc).__name__}: {exc}")
                self._log_file(project_id, traceback.format_exc())
        repo.update_project(project_id, status="partial_error" if failures else "completed", error=f"{failures}件失敗" if failures else None)
        repo.update_job(job_id, progress=100, stage="一括生成完了", status="completed", log=f"成功{len(article_ids)-failures}件 / 失敗{failures}件")

    def _video(self, job_id: str, article_id: int) -> None:
        article = repo.get_article(article_id)
        assert article and article["script"]
        project_id = article["project_id"]
        try:
            output_dir = Path(article["output_dir"])
            result = build_video(
                article["script"]["content"], output_dir, db.settings(),
                progress=lambda percent, stage: self._update(job_id, project_id, percent, stage),
            )
            repo.update_article(article_id, status="completed", video_path=str(result["video"]), thumbnail_path=str(result["thumbnail"]), video_duration=result["duration"], error=None)
            remaining = [a for a in repo.list_articles(project_id) if a["selected"] and a["status"] not in {"completed", "error"}]
            errors = [a for a in repo.list_articles(project_id) if a["selected"] and a["status"] == "error"]
            if not remaining:
                repo.update_project(project_id, status="partial_error" if errors else "completed")
            repo.update_job(job_id, progress=100, stage="生成完了", status="completed", log=f"動画時間 {result['duration']:.2f}秒")
        except Exception as exc:
            repo.update_article(article_id, status="error", error=f"{type(exc).__name__}: {exc}")
            self._fail(job_id, project_id, exc)

    def _fail(self, job_id: str, project_id: str, exc: Exception) -> None:
        detail = f"{type(exc).__name__}: {exc}"
        repo.update_job(job_id, status="error", stage="エラー", error=detail, log=detail)
        repo.update_project(project_id, status="error", error=detail)
        self._log_file(project_id, traceback.format_exc())


job_runner = JobRunner()
