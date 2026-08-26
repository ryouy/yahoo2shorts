from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime
from difflib import SequenceMatcher
from urllib.parse import quote_plus, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from ...storage.files import clean_text
from ..openai_service import openai_service
from .article_fetcher import clean_direct_urls, fetch_yahoo_article
from .browser import assert_not_geo_blocked, body_text, create_driver
from .comment_fetcher import comments_url

JST = ZoneInfo("Asia/Tokyo")
CATEGORIES = {
    "国内": "https://news.yahoo.co.jp/categories/domestic", "国際": "https://news.yahoo.co.jp/categories/world",
    "経済": "https://news.yahoo.co.jp/categories/business", "エンタメ": "https://news.yahoo.co.jp/categories/entertainment",
    "スポーツ": "https://news.yahoo.co.jp/categories/sports", "IT": "https://news.yahoo.co.jp/categories/it",
}
RANKINGS = {
    "アクセスランキング": "https://news.yahoo.co.jp/ranking/access/news",
    "コメントランキング": "https://news.yahoo.co.jp/ranking/comment/news",
}

SEARCH_PLAN_SCHEMA = {
    "type": "object", "properties": {"intent_summary": {"type": "string"}, "queries": {"type": "array", "items": {"type": "string"}}},
    "required": ["intent_summary", "queries"], "additionalProperties": False,
}
RANK_SCHEMA = {
    "type": "object", "properties": {"ranked": {"type": "array", "items": {
        "type": "object", "properties": {"url": {"type": "string"}, "score": {"type": "integer"}, "reason": {"type": "string"}},
        "required": ["url", "score", "reason"], "additionalProperties": False,
    }}}, "required": ["ranked"], "additionalProperties": False,
}


def _normalize_url(href: str) -> str | None:
    parsed = urlsplit(clean_text(href))
    if (parsed.hostname or "").lower() != "news.yahoo.co.jp" or not re.search(r"/(?:expert/)?articles/[A-Za-z0-9_-]+", parsed.path):
        return None
    return urlunsplit(("https", "news.yahoo.co.jp", parsed.path.rstrip("/"), "", ""))


def _collect_page(driver, url: str, label: str, limit: int) -> list[dict]:
    driver.get(url)
    WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
    assert_not_geo_blocked(driver, url)
    time.sleep(.35)
    result, seen = [], set()
    for anchor in driver.find_elements(By.CSS_SELECTOR, "a[href]"):
        href = _normalize_url(anchor.get_attribute("href") or "")
        if not href or href in seen:
            continue
        title = clean_text(anchor.text)
        try:
            context = clean_text(anchor.find_element(By.XPATH, "ancestor::*[self::li or self::article or self::div][1]").text)
        except Exception:
            context = title
        if title or context:
            result.append({"url": href, "title": title, "context": context[:700], "sources": [label]})
            seen.add(href)
        if len(result) >= limit:
            break
    return result


def _merge(bucket: dict, item: dict) -> None:
    existing = bucket.get(item["url"])
    if not existing:
        bucket[item["url"]] = item
        return
    if len(item.get("title", "")) > len(existing.get("title", "")):
        existing["title"] = item["title"]
    existing["sources"] = list(dict.fromkeys(existing["sources"] + item["sources"]))


def _plan_queries(request: str, model: str) -> list[str]:
    if not clean_text(request):
        return []
    data = openai_service.structured(
        model=model,
        instructions="希望するYahooニュース記事の条件から、Yahooニュース検索用の短い日本語検索語を最大4つ作る。",
        prompt=request, schema_name="yahoo_search_plan", schema=SEARCH_PLAN_SCHEMA, max_output_tokens=1000,
    )
    return list(dict.fromkeys(clean_text(query) for query in data.get("queries", []) if clean_text(query)))[:4]


def _rank(request: str, candidates: list[dict], model: str) -> dict[str, dict]:
    if not request:
        return {item["url"]: {"score": 70, "reason": "指定URL"} for item in candidates}
    payload = [{key: item.get(key) for key in ("url", "title", "context", "sources")} for item in candidates]
    data = openai_service.structured(
        model=model,
        instructions="候補を希望への適合度、60秒で理解できるか、複数意見が成立するかで0〜100点評価。候補外URLは禁止。",
        prompt=f"ユーザー希望:\n{request}\n\n候補:\n{json.dumps(payload, ensure_ascii=False)}",
        schema_name="yahoo_article_ranking", schema=RANK_SCHEMA, max_output_tokens=5000,
    )
    valid = {item["url"] for item in candidates}
    return {item["url"]: {"score": max(0, min(100, int(item["score"]))), "reason": clean_text(item["reason"])}
            for item in data.get("ranked", []) if item.get("url") in valid}


def _freshness(published_at: str | None, max_hours: int) -> tuple[float, float | None]:
    if not published_at:
        return 35.0, None
    try:
        value = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=JST)
        age = max(0, (datetime.now(value.tzinfo) - value).total_seconds() / 3600)
        return max(0, 100 * (1 - age / max(1, max_hours))), age
    except ValueError:
        return 35.0, None


def _comment_count(driver, url: str) -> int:
    try:
        driver.get(comments_url(url, 1))
        WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
        text = body_text(driver, 15000)
        values = [int(value.replace(",", "")) for value in re.findall(r"コメント\s*([\d,]+)\s*件", text)]
        visible = len(driver.find_elements(By.CSS_SELECTOR, 'div[id^="viewable_comment_middle_"]'))
        return max([visible, *values, 0])
    except Exception:
        return 0


def discover_articles(*, mode: str, request_text: str, urls: list[str], article_count: int,
                      settings: dict, progress=None) -> list[dict]:
    direct = clean_direct_urls(urls)
    bucket: dict[str, dict] = {url: {"url": url, "title": "", "context": "", "sources": ["直接URL"]} for url in direct}
    if mode != "url":
        queries = _plan_queries(request_text, settings["openai_model"])
        driver = create_driver()
        try:
            pages: list[tuple[str, str, int]] = []
            if settings["use_yahoo_top"]:
                pages.append(("https://news.yahoo.co.jp/", "Yahooトップ", 20))
            if settings["use_yahoo_ranking"]:
                pages.extend((url, f"ランキング:{name}", 24) for name, url in RANKINGS.items())
            if settings["use_yahoo_categories"]:
                pages.extend((url, f"カテゴリ:{name}", 10) for name, url in CATEGORIES.items())
            if settings["use_yahoo_search"]:
                pages.extend(("https://news.yahoo.co.jp/search?p=" + quote_plus(q), f"検索:{q}", 12) for q in queries)
            for index, (page_url, label, limit) in enumerate(pages, start=1):
                if progress:
                    progress(f"候補収集: {label}", 5 + int(25 * index / max(1, len(pages))))
                try:
                    for item in _collect_page(driver, page_url, label, limit):
                        _merge(bucket, item)
                except Exception:
                    continue
        finally:
            driver.quit()
    candidates = list(bucket.values())[:70]
    if not candidates:
        raise RuntimeError("記事候補を取得できませんでした。")
    ranking = _rank(request_text if mode != "url" else "", candidates, settings["openai_model"])
    shortlist = sorted(candidates, key=lambda item: ranking.get(item["url"], {}).get("score", 0), reverse=True)
    shortlist = shortlist[:max(22, len(direct))]
    probe_driver = create_driver()
    detailed = []
    try:
        for index, item in enumerate(shortlist, start=1):
            if progress:
                progress(f"記事詳細を確認 {index}/{len(shortlist)}", 35 + int(55 * index / len(shortlist)))
            detail = dict(item)
            try:
                article = fetch_yahoo_article(item["url"])
                detail.update({key: article.get(key) for key in ("title", "source", "published_at")})
            except Exception as exc:
                detail["probe_error"] = str(exc)
                if mode == "url":
                    continue
            count = _comment_count(probe_driver, item["url"])
            fresh, age = _freshness(detail.get("published_at"), settings["max_article_age_hours"])
            comment_score = min(100, 100 * math.log1p(count) / math.log1p(500)) if count else 0
            ai = ranking.get(item["url"], {}).get("score", 0)
            combined = ai * settings["ai_score_weight"] + comment_score * settings["comment_score_weight"] + fresh * settings["freshness_score_weight"]
            detail.update({
                "comment_count": count, "freshness_score": round(fresh, 2), "age_hours": round(age, 1) if age is not None else None,
                "comment_score": round(comment_score, 2), "ai_score": ai, "combined_score": round(combined, 2),
                "reason": ranking.get(item["url"], {}).get("reason", "ユーザーがURLを直接指定"),
                "discovery_source": " / ".join(item.get("sources", [])),
            })
            detailed.append(detail)
    finally:
        probe_driver.quit()
    if not detailed:
        raise RuntimeError("指定されたYahooニュース記事を確認できませんでした。URLと公開状態を確認してください。")
    detailed.sort(key=lambda item: (item["url"] not in direct, -item["combined_score"]))
    selected: list[dict] = []
    for item in detailed:
        title = re.sub(r"[\s【】「」（）・!！?？]", "", item.get("title", "")).lower()
        if item["url"] not in direct and any(SequenceMatcher(None, title, re.sub(r"[\s【】「」（）・!！?？]", "", x.get("title", "")).lower()).ratio() >= .86 for x in selected):
            continue
        selected.append(item)
        if len(selected) >= (len(direct) if mode == "url" else article_count):
            break
    return selected
