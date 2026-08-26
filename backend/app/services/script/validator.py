from __future__ import annotations

from ...core.exceptions import ValidationError
from ...storage.files import clean_text


def estimate_tts_seconds(text: str) -> float:
    value = clean_text(text)
    return 0.0 if not value else 0.45 + len(value) / 7.6


def estimate_script_seconds(script: dict) -> float:
    total = estimate_tts_seconds(script.get("intro", {}).get("narration", "")) + .05
    total += sum(estimate_tts_seconds(post.get("text", "")) + .05 for post in script.get("posts", []))
    total += estimate_tts_seconds(script.get("outro", {}).get("narration", "")) + .05
    return round(total, 1)


def validate_script(script: dict, valid_comment_ids: set[str], settings: dict, *, editor: bool = False) -> None:
    posts = script.get("posts")
    if not isinstance(posts, list):
        raise ValidationError("posts が配列ではありません。")
    minimum, maximum = ((1, 20) if editor else (settings["thread_post_min"], settings["thread_post_max"]))
    if not minimum <= len(posts) <= maximum:
        raise ValidationError(f"コメントは{minimum}〜{maximum}件必要です。")
    short_count = reply_count = 0
    for index, post in enumerate(posts, 1):
        text = clean_text(post.get("text"))
        if not text:
            raise ValidationError(f"レス{index}が空です。")
        if not editor and len(text) > settings["post_max_chars"]:
            raise ValidationError(f"レス{index}が長すぎます（{len(text)}文字）。")
        if 5 <= len(text) <= 15:
            short_count += 1
        reply_to = post.get("reply_to")
        if reply_to is not None:
            reply_count += 1
            if not isinstance(reply_to, int) or not 1 <= reply_to < index:
                raise ValidationError(f"レス{index}の返信先が不正です。")
        importance = int(post.get("importance", 3))
        if not 1 <= importance <= 5:
            raise ValidationError(f"レス{index}の重要度が不正です。")
        source_ids = [clean_text(value) for value in post.get("source_comment_ids", []) if clean_text(value)]
        if not editor and not source_ids:
            raise ValidationError(f"レス{index}に根拠コメントIDがありません。")
        unknown = set(source_ids) - valid_comment_ids
        if valid_comment_ids and unknown:
            raise ValidationError(f"レス{index}に未知のコメントIDがあります。")
    if not editor:
        if short_count < 2:
            raise ValidationError("5〜15文字の短いレスが2件以上必要です。")
        if not settings["min_reply_posts"] <= reply_count <= settings["max_reply_posts"]:
            raise ValidationError("返信レス数が設定範囲外です。")
        if estimate_script_seconds(script) > 54:
            raise ValidationError("推定動画時間が長すぎます。")

