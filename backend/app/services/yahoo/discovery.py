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
    "type": "object", "properties": {
        "queries": {"type": "array", "items": {"type": "string"}},
        "must_terms": {"type": "array", "items": {"type": "string"}},
        "exclude_terms": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["queries", "must_terms", "exclude_terms"], "additionalProperties": False,
}
RANK_SCHEMA = {
    "type": "object", "properties": {"ranked": {"type": "array", "items": {
        "type": "object", "properties": {"url": {"type": "string"}, "score": {"type": "integer"}, "reason": {"type": "string"}},
        "required": ["url", "score", "reason"], "additionalProperties": False,
    }}}, "required": ["ranked"], "additionalProperties": False,
}
FINAL_RELEVANCE_SCHEMA = {
    "type": "object", "properties": {"ranked": {"type": "array", "items": {
        "type": "object", "properties": {
            "url": {"type": "string"}, "score": {"type": "integer"}, "reason": {"type": "string"},
            "relevant": {"type": "boolean"},
        },
        "required": ["url", "score", "reason", "relevant"], "additionalProperties": False,
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


def _fallback_query(request: str) -> str:
    """Keep the user's wording in the search plan even when AI planning fails."""
    value = clean_text(request)
    value = re.sub(r"(?:の記事)?を?\s*\d+\s*(?:本|件)", "", value)
    return value[:100]


def _local_query_variants(request: str) -> list[str]:
    """Derive usable Yahoo query variants without relying on an LLM response.

    Natural-language prompts often include instructions ("find me", count,
    format) that reduce a site-search match.  This keeps the user's wording
    and adds one compact topic query made from the remaining concepts.
    """
    original = _fallback_query(request)
    compact = original
    compact = re.sub(r"(?:について|に関する|に関して|をテーマに|を探(?:して|したい)|を教えて|が知りたい)", " ", compact)
    compact = re.sub(r"(?:ニュース|記事|話題|報道)(?:を|が|に|で)?", " ", compact)
    compact = re.sub(r"(?:比較|解説|最新|直近|炎上|コメント|反応)(?:できる|の)?", lambda match: f" {match.group(0).replace('できる', '').replace('の', '')} ", compact)
    compact = re.sub(r"[、。,.，/｜|]+", " ", compact)
    compact = re.sub(r"\s+", " ", compact).strip()
    variants = [original]
    if len(compact.replace(" ", "")) >= 2:
        variants.append(compact[:70])
    # Quoted words are usually the strongest intent signal in Japanese prompts.
    variants.extend(clean_text(value) for value in re.findall(r"[「『\"]([^」』\"]+)[」』\"]", request))
    return list(dict.fromkeys(value for value in variants if value))[:4]


def _plan_search(request: str, model: str) -> dict[str, list[str]]:
    fallback = _fallback_query(request)
    plan = {"queries": _local_query_variants(request), "must_terms": [], "exclude_terms": []}
    if not fallback:
        return plan
    try:
        data = openai_service.structured(
            model=model,
            instructions=(
                "ユーザーが求めるYahooニュース記事を正確に探す検索計画を作成する。"
                "queriesは日本語の短い検索語を最大4個。must_termsには記事に必須の固有名詞・出来事・条件だけを入れる。"
                "exclude_termsには明確に不要な話題だけを入れる。抽象語や推測は追加しない。"
            ),
            prompt=request, schema_name="yahoo_search_plan", schema=SEARCH_PLAN_SCHEMA, max_output_tokens=1000,
        )
        for key, limit in (("queries", 5), ("must_terms", 6), ("exclude_terms", 6)):
            values = [clean_text(item) for item in data.get(key, []) if clean_text(item)]
            prefix = _local_query_variants(request) if key == "queries" else []
            plan[key] = list(dict.fromkeys(prefix + values))[:limit]
    except Exception:
        # Search can still proceed with the request itself if planning is
        # temporarily unavailable; this is preferable to collecting unrelated
        # ranking-page articles.
        pass
    return plan


def _term_relevance(item: dict, must_terms: list[str], exclude_terms: list[str]) -> float:
    text = clean_text(" ".join(str(item.get(key) or "") for key in ("title", "context", "body"))).lower()
    if not text:
        return 0.0
    excluded = sum(1 for term in exclude_terms if term.lower() in text)
    if excluded:
        return max(0.0, 20.0 - excluded * 20.0)
    if not must_terms:
        return 50.0 if "検索:" in str(item.get("sources", "")) else 35.0
    matched = sum(1 for term in must_terms if term.lower() in text)
    title_matches = sum(1 for term in must_terms if term.lower() in clean_text(item.get("title")).lower())
    return min(100.0, 100.0 * matched / len(must_terms) + 12.0 * title_matches)


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


def _safe_rank(request: str, candidates: list[dict], model: str) -> dict[str, dict]:
    try:
        return _rank(request, candidates, model)
    except Exception:
        return {}


def _final_relevance(request: str, candidates: list[dict], model: str) -> dict[str, dict]:
    """Judge fetched articles against the request, rather than their headlines."""
    if not candidates:
        return {}
    payload = [
        {"url": item["url"], "title": item.get("title", ""), "source": item.get("source", ""),
         "excerpt": clean_text(item.get("body") or item.get("context"))[:1100]}
        for item in candidates
    ]
    try:
        data = openai_service.structured(
            model=model,
            instructions=(
                "ユーザーの希望に対して、各Yahooニュース記事が実際に適合するかを厳密に判定する。"
                "タイトルの単語一致だけでrelevant=trueにしない。本文抜粋が希望する人物・出来事・条件を扱う時だけtrue。"
                "無関係、周辺話題、古い別件はfalse。すべての入力URLを1件ずつ返す。"
            ),
            prompt=f"ユーザー希望:\n{request}\n\n記事候補:\n{json.dumps(payload, ensure_ascii=False)}",
            schema_name="yahoo_article_relevance", schema=FINAL_RELEVANCE_SCHEMA, max_output_tokens=6000,
        )
    except Exception:
        return {}
    valid = {item["url"] for item in candidates}
    return {
        item["url"]: {"score": max(0, min(100, int(item["score"]))), "reason": clean_text(item["reason"]), "relevant": bool(item["relevant"])}
        for item in data.get("ranked", []) if item.get("url") in valid
    }


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
    plan = {"queries": [], "must_terms": [], "exclude_terms": []}
    if mode != "url":
        plan = _plan_search(request_text, settings["openai_model"])
        driver = create_driver()
        try:
            pages: list[tuple[str, str, int]] = []
            # Intent-specific Yahoo search results are collected first. Generic
            # pages remain a backup source, never the primary interpretation of
            # the user's request.
            if settings["use_yahoo_search"]:
                pages.extend(("https://news.yahoo.co.jp/search?p=" + quote_plus(query), f"検索:{query}", 30) for query in plan["queries"])
            if settings["use_yahoo_top"]:
                pages.append(("https://news.yahoo.co.jp/", "Yahooトップ", 20))
            if settings["use_yahoo_ranking"]:
                pages.extend((url, f"ランキング:{name}", 24) for name, url in RANKINGS.items())
            if settings["use_yahoo_categories"]:
                pages.extend((url, f"カテゴリ:{name}", 10) for name, url in CATEGORIES.items())
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
    candidates = list(bucket.values())[:150]
    if not candidates:
        raise RuntimeError("記事候補を取得できませんでした。")
    initial_pool = sorted(
        candidates,
        key=lambda item: _term_relevance(item, plan["must_terms"], plan["exclude_terms"]),
        reverse=True,
    )[:60]
    ranking = _safe_rank(request_text if mode != "url" else "", initial_pool, settings["openai_model"])
    for candidate in candidates:
        lexical = _term_relevance(candidate, plan["must_terms"], plan["exclude_terms"])
        ai_score = ranking.get(candidate["url"], {}).get("score", 0)
        candidate["intent_score"] = round(max(lexical, ai_score * .8 + lexical * .2), 2)
    shortlist = sorted(candidates, key=lambda item: item["intent_score"], reverse=True)
    # Fetch enough article bodies for meaningful relevance validation; 22 was
    # too small when Yahoo's first page contains broad or sponsored results.
    shortlist = shortlist[:max(42, len(direct))]
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
                detail["body"] = clean_text(article.get("body"))[:1400]
                detail["context"] = detail["body"] or detail.get("context", "")
            except Exception as exc:
                detail["probe_error"] = str(exc)
                if mode == "url":
                    continue
            count = _comment_count(probe_driver, item["url"])
            fresh, age = _freshness(detail.get("published_at"), settings["max_article_age_hours"])
            comment_score = min(100, 100 * math.log1p(count) / math.log1p(500)) if count else 0
            ai = ranking.get(item["url"], {}).get("score", item.get("intent_score", 0))
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
    if mode != "url":
        final_ranking = _safe_rank(request_text, detailed, settings["openai_model"])
        relevance = _final_relevance(request_text, detailed, settings["openai_model"])
        for item in detailed:
            lexical = _term_relevance(item, plan["must_terms"], plan["exclude_terms"])
            final_ai = final_ranking.get(item["url"], {}).get("score", 0)
            verdict = relevance.get(item["url"], {})
            # A retrieved article must satisfy the intent too; popularity and
            # freshness only decide between relevant candidates.
            item["relevant"] = verdict.get("relevant", True)
            item["ai_score"] = round(max(lexical, final_ai * .55 + lexical * .2 + verdict.get("score", 0) * .25), 2)
            item["reason"] = verdict.get("reason") or final_ranking.get(item["url"], {}).get("reason") or ranking.get(item["url"], {}).get("reason") or "テーマとの関連性を確認"
            item["combined_score"] = round(
                item["ai_score"] * settings["ai_score_weight"]
                + item["comment_score"] * settings["comment_score_weight"]
                + item["freshness_score"] * settings["freshness_score_weight"],
                2,
            )
    if mode != "url" and any(item.get("relevant") is True for item in detailed):
        # Only enforce the AI gate when it returned at least one positive result;
        # an interrupted or partial model response must not make search empty.
        detailed = [item for item in detailed if item.get("relevant") is True]
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
