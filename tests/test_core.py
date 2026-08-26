from pathlib import Path

import pytest

from backend.app.services.script.validator import estimate_script_seconds, validate_script
from backend.app.services.script.generator import normalize_generated_script
from backend.app.services.media.renderer import _background
from backend.app.services.media.tts import require_binary
from backend.app.services.yahoo.article_fetcher import clean_direct_urls, extract_article, validate_yahoo_url
from backend.app.services.yahoo.comment_fetcher import _click_more, comments_url, parse_yahoo_datetime
from backend.app.storage.files import safe_title_stem
from run import open_in_chrome


def test_yahoo_url_validation_and_deduplication():
    url = "https://news.yahoo.co.jp/articles/abc123"
    assert validate_yahoo_url(url) == url
    assert clean_direct_urls([url, url + "?source=test"]) == [url]
    with pytest.raises(ValueError):
        validate_yahoo_url("https://example.com/articles/abc123")


def test_article_jsonld_extraction():
    html = '''
    <html><head><script type="application/ld+json">
    {"@type":"NewsArticle","headline":"テスト記事","articleBody":"%s","publisher":{"name":"テスト新聞"},"datePublished":"2026-08-26T12:00:00+09:00"}
    </script></head></html>
    ''' % ("本文です。" * 80)
    article = extract_article(html, "https://news.yahoo.co.jp/articles/test")
    assert article["title"] == "テスト記事"
    assert article["source"] == "テスト新聞"
    assert len(article["body"]) > 300


def test_safe_title_stem_removes_unsafe_characters():
    assert safe_title_stem('危険:/記事*?"<>|', 20) == "危険記事"


def test_editor_script_validation_and_estimate():
    script = {
        "intro": {"narration": "記事を短く説明します"},
        "posts": [
            {"text": "これはどうなんだ", "reply_to": None, "importance": 3, "source_comment_ids": []},
            {"text": "いや無理ある", "reply_to": 1, "importance": 3, "source_comment_ids": []},
        ],
        "outro": {"narration": "あなたはどう思う"},
    }
    settings = {"thread_post_min": 6, "thread_post_max": 9, "post_max_chars": 48, "min_reply_posts": 1, "max_reply_posts": 3}
    validate_script(script, set(), settings, editor=True)
    assert 0 < estimate_script_seconds(script) < 20


def test_renderer_background_all_variants():
    for variant in range(5):
        image = _background(108, 192, variant)
        assert image.size == (108, 192)


def test_comments_url_and_relative_datetime():
    assert comments_url("https://news.yahoo.co.jp/articles/abc", 3).endswith("/comments?page=3")
    assert parse_yahoo_datetime("2時間前") is not None


def test_generated_script_aliases_and_reply_count_are_repaired():
    result = {
        "posts": [
            {"text": "最初の意見です", "reply_to": None, "tone": "serious", "importance": 4, "source_comment_ids": ["c001"]},
            {"text": "それは違うだろ", "reply_to": None, "tone": "counter", "importance": 3, "source_comment_ids": ["c002", "invented"]},
        ]
    }
    settings = {"min_reply_posts": 1, "max_reply_posts": 3}
    normalized = normalize_generated_script(result, {"c001": "real-1", "c002": "real-2"}, settings)
    assert normalized["posts"][0]["source_comment_ids"] == ["real-1"]
    assert normalized["posts"][1]["source_comment_ids"] == ["real-2"]
    assert normalized["posts"][1]["reply_to"] == 1
    assert normalized["validation_warnings"]


def test_click_more_uses_each_discovered_element():
    class Driver:
        def __init__(self):
            self.elements = [object(), object()]
            self.clicked = []

        def find_elements(self, *_args):
            return self.elements

        def execute_script(self, _script, element):
            self.clicked.append(element)

    driver = Driver()
    _click_more(driver)
    assert driver.clicked == driver.elements


def test_require_binary_uses_platform_fallback(monkeypatch, tmp_path):
    executable = tmp_path / "ffprobe"
    executable.write_text("test")
    monkeypatch.setattr("backend.app.services.media.tts.find_executable", lambda _name: str(executable))
    assert require_binary("ffprobe") == str(executable)


def test_launcher_opens_chrome_directly(monkeypatch):
    launched = []
    monkeypatch.setattr("run.find_chrome_binary", lambda: "/Applications/Google Chrome")
    monkeypatch.setattr("run.subprocess.Popen", lambda command, **kwargs: launched.append((command, kwargs)))
    assert open_in_chrome("http://127.0.0.1:8000") is True
    assert launched[0][0] == ["/Applications/Google Chrome", "--new-tab", "http://127.0.0.1:8000"]
