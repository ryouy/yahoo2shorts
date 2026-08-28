from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = Path(os.getenv("YSS_DATA_DIR", ROOT_DIR / "data")).expanduser().resolve()
RUNS_DIR = DATA_DIR / "runs"
DB_PATH = DATA_DIR / "app.db"


@dataclass(slots=True)
class AppSettings:
    article_count: int = 3
    output_folder: str = str(RUNS_DIR)
    openai_model: str = "gpt-5.6-luna"
    comment_limit: int = 45
    include_replies: bool = True
    max_comment_pages: int = 50
    min_comments_for_script: int = 6
    max_article_age_hours: int = 72
    use_yahoo_search: bool = True
    use_yahoo_top: bool = True
    use_yahoo_ranking: bool = True
    use_yahoo_categories: bool = True
    ai_score_weight: float = 0.40
    comment_score_weight: float = 0.35
    freshness_score_weight: float = 0.25
    thread_post_min: int = 6
    thread_post_max: int = 9
    post_max_chars: int = 48
    min_reply_posts: int = 1
    max_reply_posts: int = 3
    target_video_seconds: float = 55.0
    hard_max_video_seconds: float = 59.5
    voice_female: str = "ja-JP-NanamiNeural"
    voice_male: str = "ja-JP-KeitaNeural"
    voice_1: str = "ja-JP-NanamiNeural"
    voice_2: str = "ja-JP-KeitaNeural"
    voice_3: str = "ja-JP-AoiNeural"
    voice_4: str = "ja-JP-DaichiNeural"
    voice_5: str = "ja-JP-MayuNeural"
    voice_6: str = "ja-JP-NaokiNeural"
    voice_rate: str = "+22%"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    comments_per_page: int = 3
    bgm_enabled: bool = True
    bgm_volume: float = 0.052
    bgm_bpm: int = 158

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_SETTINGS = AppSettings().to_dict()


def ensure_data_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
