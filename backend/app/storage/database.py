from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from ..core.config import DB_PATH, DEFAULT_SETTINGS, ensure_data_dirs


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'created',
  request_mode TEXT NOT NULL DEFAULT 'url',
  request_text TEXT NOT NULL DEFAULT '',
  article_count INTEGER NOT NULL DEFAULT 1,
  video_mode TEXT NOT NULL DEFAULT 'normal',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  error TEXT
);

CREATE TABLE IF NOT EXISTS articles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  url TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  published_at TEXT,
  age_hours REAL,
  comment_count INTEGER NOT NULL DEFAULT 0,
  ai_score REAL NOT NULL DEFAULT 0,
  comment_score REAL NOT NULL DEFAULT 0,
  freshness_score REAL NOT NULL DEFAULT 0,
  combined_score REAL NOT NULL DEFAULT 0,
  reason TEXT NOT NULL DEFAULT '',
  discovery_source TEXT NOT NULL DEFAULT '',
  selected INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'candidate',
  output_dir TEXT,
  article_path TEXT,
  comments_path TEXT,
  draft_path TEXT,
  approved_path TEXT,
  video_path TEXT,
  thumbnail_path TEXT,
  video_duration REAL,
  bgm_track TEXT,
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(project_id, url)
);

CREATE TABLE IF NOT EXISTS scripts (
  article_id INTEGER PRIMARY KEY REFERENCES articles(id) ON DELETE CASCADE,
  content_json TEXT NOT NULL,
  approved INTEGER NOT NULL DEFAULT 0,
  estimated_seconds REAL NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
  article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  progress INTEGER NOT NULL DEFAULT 0,
  stage TEXT NOT NULL DEFAULT '待機中',
  logs_json TEXT NOT NULL DEFAULT '[]',
  error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value_json TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_articles_project ON articles(project_id);
CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project_id);
"""


class Database:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        self._write_lock = threading.RLock()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self) -> None:
        ensure_data_dirs()
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            existing_columns = {row["name"] for row in connection.execute("PRAGMA table_info(projects)")}
            if "video_mode" not in existing_columns:
                connection.execute("ALTER TABLE projects ADD COLUMN video_mode TEXT NOT NULL DEFAULT 'normal'")
            article_columns = {row["name"] for row in connection.execute("PRAGMA table_info(articles)")}
            if "bgm_track" not in article_columns:
                connection.execute("ALTER TABLE articles ADD COLUMN bgm_track TEXT")
            # A failed regeneration must not hide a previously saved draft.
            connection.execute(
                "UPDATE articles SET status=CASE "
                "WHEN (SELECT s.approved FROM scripts s WHERE s.article_id=articles.id)=1 "
                "THEN 'ready_for_video' ELSE 'waiting_script_approval' END, "
                "error=NULL, updated_at=? "
                "WHERE status IN ('error','waiting_script_approval') AND video_path IS NULL "
                "AND id IN (SELECT article_id FROM scripts)",
                (utc_now(),),
            )
            # Once article drafts are recoverable, clear the stale project-level failure too.
            connection.execute(
                "UPDATE projects SET status=CASE "
                "WHEN EXISTS(SELECT 1 FROM articles a JOIN scripts s ON s.article_id=a.id "
                "  WHERE a.project_id=projects.id AND a.selected=1 AND s.approved=0) "
                "THEN 'waiting_script_approval' ELSE 'ready_for_video' END, "
                "error=NULL, updated_at=? "
                "WHERE status IN ('error','partial_error') "
                "AND EXISTS(SELECT 1 FROM articles a JOIN scripts s ON s.article_id=a.id "
                "  WHERE a.project_id=projects.id AND a.selected=1) "
                "AND NOT EXISTS(SELECT 1 FROM articles a WHERE a.project_id=projects.id AND a.status='error')",
                (utc_now(),),
            )
            for key, value in DEFAULT_SETTINGS.items():
                connection.execute(
                    "INSERT OR IGNORE INTO settings(key,value_json,updated_at) VALUES(?,?,?)",
                    (key, json.dumps(value, ensure_ascii=False), utc_now()),
                )
            # Retired Japanese voice IDs used by earlier desktop releases
            # return empty audio. Replace only those old defaults; custom values
            # remain intact and are still protected by TTS fallback at runtime.
            retired_voices = {
                "ja-JP-AoiNeural": "en-US-AvaMultilingualNeural",
                "ja-JP-DaichiNeural": "en-US-AndrewMultilingualNeural",
                "ja-JP-MayuNeural": "en-US-EmmaMultilingualNeural",
                "ja-JP-NaokiNeural": "en-US-BrianMultilingualNeural",
            }
            for old_voice, new_voice in retired_voices.items():
                connection.execute(
                    "UPDATE settings SET value_json=?,updated_at=? WHERE key IN ('voice_1','voice_2','voice_3','voice_4','voice_5','voice_6') AND value_json=?",
                    (json.dumps(new_voice, ensure_ascii=False), utc_now(), json.dumps(old_voice, ensure_ascii=False)),
                )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._write_lock, self.connect() as connection:
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(sql, params).fetchone()
            return dict(row) if row else None

    def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        with self.connect() as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]

    def execute(self, sql: str, params: tuple = ()) -> int:
        with self.transaction() as connection:
            cursor = connection.execute(sql, params)
            return int(cursor.lastrowid or 0)

    def settings(self) -> dict[str, Any]:
        rows = self.fetchall("SELECT key,value_json FROM settings")
        values = dict(DEFAULT_SETTINGS)
        for row in rows:
            values[row["key"]] = json.loads(row["value_json"])
        return values

    def update_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        allowed = set(DEFAULT_SETTINGS)
        now = utc_now()
        with self.transaction() as connection:
            for key, value in values.items():
                if key not in allowed:
                    continue
                connection.execute(
                    "INSERT INTO settings(key,value_json,updated_at) VALUES(?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at",
                    (key, json.dumps(value, ensure_ascii=False), now),
                )
        return self.settings()


db = Database()
