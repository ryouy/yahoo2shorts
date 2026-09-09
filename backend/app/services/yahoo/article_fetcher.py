from __future__ import annotations

import json
import logging
import re
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps
from requests.adapters import HTTPAdapter
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from urllib3.util.retry import Retry

from ...core.exceptions import YahooFetchError, YahooGeoBlockedError
from ...storage.files import clean_text
from .browser import GEO_MARKERS, assert_not_geo_blocked, browser_user_agent, create_driver

ARTICLE_TYPES = {"Article", "NewsArticle", "ReportageNewsArticle", "AnalysisNewsArticle", "OpinionNewsArticle"}
logger = logging.getLogger(__name__)


def validate_yahoo_url(url: str) -> str:
    url = clean_text(url)
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() != "news.yahoo.co.jp":
        raise ValueError("news.yahoo.co.jp のURLを入力してください。")
    if "/articles/" not in parsed.path:
        raise ValueError("Yahooニュースの記事URL形式ではありません。")
    return url


def clean_direct_urls(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        url = validate_yahoo_url(value)
        normalized = url.split("?", 1)[0].rstrip("/")
        if normalized not in result:
            result.append(normalized)
    return result


def _jsonld_nodes(value):
    if isinstance(value, list):
        for item in value:
            yield from _jsonld_nodes(item)
    elif isinstance(value, dict):
        yield value
        yield from _jsonld_nodes(value.get("@graph", []))


def _jsonld_article(soup: BeautifulSoup) -> dict:
    candidates = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or script.get_text())
        except Exception:
            continue
        for node in _jsonld_nodes(data):
            node_type = node.get("@type")
            types = set(node_type if isinstance(node_type, list) else [node_type])
            if types & ARTICLE_TYPES:
                candidates.append((len(str(node.get("articleBody", ""))), node))
    return max(candidates, default=(0, {}), key=lambda item: item[0])[1]


def _name(value) -> str:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, dict):
        return clean_text(value.get("name"))
    if isinstance(value, list):
        return " / ".join(filter(None, (_name(item) for item in value)))
    return ""


def _meta(soup: BeautifulSoup, **attrs) -> str:
    tag = soup.find("meta", attrs=attrs)
    return clean_text(tag.get("content", "")) if tag else ""


def _image_url(value) -> str:
    if isinstance(value, str):
        return clean_text(value)
    if isinstance(value, list):
        return next((item for item in (_image_url(item) for item in value) if item), "")
    if isinstance(value, dict):
        return clean_text(value.get("url") or value.get("contentUrl"))
    return ""


def _dom_body(soup: BeautifulSoup) -> str:
    reject = re.compile(r"comment|related|recommend|ranking|share|sns|profile|author|navigation|footer|advert", re.I)
    best = ""
    for selector in ('[itemprop="articleBody"]', '[class*="articleBody"]', '[class*="ArticleBody"]', "main article", "article", "main"):
        for original in soup.select(selector):
            fragment = BeautifulSoup(str(original), "html.parser")
            for bad in fragment.select("script,style,nav,footer,aside,form,button,noscript,iframe"):
                bad.decompose()
            for tag in reversed(list(fragment.find_all(True))):
                ident = " ".join((str(tag.get("id") or ""), " ".join(tag.get("class") or [])))
                if ident and reject.search(ident):
                    tag.decompose()
            lines, seen = [], set()
            for element in fragment.select("h2,h3,p"):
                text = clean_text(element.get_text(" ", strip=True))
                if len(text) >= 4 and text not in seen and not text.startswith(("関連記事", "おすすめの記事", "コメント")):
                    seen.add(text)
                    lines.append(text)
            candidate = "\n".join(lines)
            if len(candidate) > len(best):
                best = candidate
    return best


def extract_article(html: str, url: str) -> dict:
    if any(marker in html for marker in GEO_MARKERS):
        raise YahooGeoBlockedError("Yahooの地域制限ページを検出しました。")
    soup = BeautifulSoup(html, "html.parser")
    node = _jsonld_article(soup)
    title = clean_text(node.get("headline") or node.get("name")) or _meta(soup, property="og:title")
    if not title and soup.find("h1"):
        title = clean_text(soup.find("h1").get_text(" ", strip=True))
    source = _name(node.get("publisher")) or _meta(soup, property="og:site_name") or "ニュース"
    if "yahoo" in source.lower():
        source = "ニュース"
    body_value = node.get("articleBody") or ""
    body = clean_text("\n".join(body_value) if isinstance(body_value, list) else body_value)
    if len(body) < 200:
        dom_body = _dom_body(soup)
        if len(dom_body) > len(body):
            body = dom_body
    canonical = soup.find("link", rel="canonical")
    return {
        "title": title,
        "source": source,
        "author": _name(node.get("author")),
        "url": clean_text(canonical.get("href")) if canonical else url,
        "body": body,
        "published_at": clean_text(node.get("datePublished") or node.get("dateCreated")) or None,
        "image_url": _image_url(node.get("image")) or _meta(soup, property="og:image"),
    }


def download_article_image(article: dict, output: Path, *, timeout: int = 15) -> Path | None:
    """Persist the article's own key visual for the generated video and thumbnail."""
    image_url = clean_text(article.get("image_url"))
    if urlsplit(image_url).scheme not in {"http", "https"}:
        return None
    try:
        # Some publisher CDNs occasionally return a broken gzip/deflate body.  Images
        # do not benefit from HTTP compression, so request the original bytes instead.
        response = requests.get(
            image_url,
            headers={"User-Agent": browser_user_agent(), "Accept-Encoding": "identity"},
            timeout=timeout,
        )
        response.raise_for_status()
        if len(response.content) > 12 * 1024 * 1024:
            return None
        with Image.open(BytesIO(response.content)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((1920, 1920), Image.Resampling.LANCZOS)
            output.parent.mkdir(parents=True, exist_ok=True)
            image.save(output, "JPEG", quality=90, optimize=True)
        return output
    except requests.exceptions.ContentDecodingError as exc:
        logger.warning("Article image skipped because the server sent an invalid compressed response: %s", exc)
        return None
    except Exception as exc:
        logger.info("Article image download skipped: %s", exc)
        return None


def fetch_yahoo_article(url: str, *, timeout: int = 20) -> dict:
    url = validate_yahoo_url(url)
    retry = Retry(total=2, backoff_factor=.8, status_forcelist=[429, 500, 502, 503, 504])
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    try:
        response = session.get(url, headers={"User-Agent": browser_user_agent(), "Accept-Language": "ja-JP"}, timeout=timeout)
        response.raise_for_status()
        article = extract_article(response.text, response.url)
        if article["title"] and len(article["body"]) >= 300:
            return article
    except YahooGeoBlockedError:
        raise
    except Exception:
        pass
    driver = create_driver(page_timeout=timeout)
    browser_title = ""
    try:
        driver.get(url)
        WebDriverWait(driver, timeout).until(lambda d: d.execute_script("return document.readyState") == "complete")
        assert_not_geo_blocked(driver, url)
        browser_title = clean_text(driver.title)
        time.sleep(.7)
        article = extract_article(driver.page_source, driver.current_url)
    finally:
        driver.quit()
    if not article["title"]:
        article["title"] = re.sub(r"\s*[-｜|]\s*ニュース.*$", "", browser_title).strip()
    if not article["title"] or len(article["body"]) < 100:
        raise YahooFetchError("記事本文を十分に取得できませんでした。Yahoo側DOMが変更された可能性があります。")
    return article
