from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.storage.database import db
from backend.app.storage.repository import repo


def test_project_crud_api(tmp_path):
    original_path = db.path
    db.path = tmp_path / "test.db"
    try:
        with TestClient(app) as client:
            created = client.post("/api/projects", json={"mode": "url", "urls": ["https://news.yahoo.co.jp/articles/test"], "article_count": 1})
            assert created.status_code == 201
            project_id = created.json()["id"]
            articles = repo.replace_candidates(project_id, [{"url": "https://news.yahoo.co.jp/articles/test", "title": "テスト記事"}])
            repo.save_script(articles[0]["id"], {
                "title": "テスト記事", "source": "ニュース", "url": articles[0]["url"],
                "intro": {"headline": "見出し", "explainer": "説明", "narration": "ナレーション"},
                "posts": [{"text": "コメント", "reply_to": None, "tone": "rough", "importance": 3, "source_comment_ids": ["c1"]}],
                "outro": {"text": "意見は？", "narration": "意見を聞かせて"}, "estimated_seconds": 5.0,
            })
            repo.update_article(articles[0]["id"], selected=1, status="error", error="再生成失敗")
            repo.update_project(project_id, status="error", error="再生成失敗")
            db.initialize()
            fetched = client.get(f"/api/projects/{project_id}")
            assert fetched.status_code == 200
            assert fetched.json()["status"] == "waiting_script_approval"
            assert fetched.json()["error"] is None
            assert fetched.json()["articles"][0]["script"]["content"]["title"] == "テスト記事"
            assert fetched.json()["articles"][0]["status"] == "waiting_script_approval"
            assert fetched.json()["articles"][0]["error"] is None
            listed = client.get("/api/projects")
            assert listed.status_code == 200
            assert listed.json()["projects"][0]["id"] == project_id
            deleted = client.delete(f"/api/projects/{project_id}")
            assert deleted.status_code == 204
            assert client.get(f"/api/projects/{project_id}").status_code == 404
    finally:
        db.path = original_path


def test_project_api_rejects_invalid_input_and_duplicate_jobs(tmp_path):
    original_path = db.path
    db.path = tmp_path / "test.db"
    try:
        with TestClient(app) as client:
            empty = client.post("/api/projects", json={"mode": "url", "urls": []})
            assert empty.status_code == 422

            invalid = client.post("/api/projects", json={"mode": "url", "urls": ["https://example.com/not-yahoo"]})
            assert invalid.status_code == 422

            created = client.post("/api/projects", json={
                "mode": "url",
                "urls": [
                    "https://news.yahoo.co.jp/articles/test?source=one",
                    "https://news.yahoo.co.jp/articles/test",
                ],
            })
            assert created.status_code == 201
            project_id = created.json()["id"]
            assert client.get(f"/api/projects/{project_id}").json()["request_text"] == "https://news.yahoo.co.jp/articles/test"

            article = repo.replace_candidates(project_id, [{"url": "https://news.yahoo.co.jp/articles/test", "title": "テスト記事"}])[0]
            repo.approve_articles(project_id, [article["id"]])
            repo.create_job("article_discovery", project_id)
            blocked = client.post(f"/api/projects/{project_id}/generate-scripts")
            assert blocked.status_code == 409
            assert "処理中のジョブ" in blocked.json()["detail"]
    finally:
        db.path = original_path
