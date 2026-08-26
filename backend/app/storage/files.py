from __future__ import annotations

import json
import re
import shutil
from pathlib import Path


def clean_text(value: object) -> str:
    text = str(value or "").replace("\u3000", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def safe_title_stem(title: str, max_chars: int = 28) -> str:
    title = clean_text(title).replace("\n", " ")
    title = re.sub(r'[\\/:*?"<>|]', "", title)
    title = re.sub(r"[\x00-\x1f]", "", title).strip(" .")
    return (title or "記事")[:max_chars]


def unique_article_dir(root: Path, title: str, article_id: int) -> Path:
    return root / f"{safe_title_stem(title)}_{article_id:03d}"


def save_json(data: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def create_project_zip(run_dir: Path) -> Path:
    archive = run_dir.parent / f"{run_dir.name}"
    result = shutil.make_archive(str(archive), "zip", root_dir=run_dir)
    return Path(result)

