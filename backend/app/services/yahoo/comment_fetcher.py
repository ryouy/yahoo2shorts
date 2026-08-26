from __future__ import annotations

import hashlib
import math
import re
import time
from datetime import datetime, timedelta
from functools import partial
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from ...core.exceptions import CommentFetchError
from ...storage.files import clean_text
from .article_fetcher import validate_yahoo_url
from .browser import assert_not_geo_blocked, body_text, create_driver

JST = ZoneInfo("Asia/Tokyo")


def comments_url(article_url: str, page: int = 1) -> str:
    parsed = urlsplit(article_url)
    path = parsed.path.rstrip("/").removesuffix("/comments")
    return urlunsplit((parsed.scheme, parsed.netloc, f"{path}/comments", f"page={page}", ""))


def parse_yahoo_datetime(text: str, reference: datetime | None = None) -> datetime | None:
    value = clean_text(text)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=JST) if parsed.tzinfo is None else parsed
    except ValueError:
        pass
    now = datetime.now(JST)
    relative = re.search(r"(\d+)\s*(分|時間|日)前", value)
    if relative:
        amount = int(relative.group(1))
        delta = {"分": timedelta(minutes=amount), "時間": timedelta(hours=amount), "日": timedelta(days=amount)}[relative.group(2)]
        return now - delta
    if "たった今" in value:
        return now
    match = re.search(r"(?:(\d{4})[/-])?(\d{1,2})/(\d{1,2}).*?(\d{1,2}):(\d{2})", value)
    if not match:
        return None
    year, month, day, hour, minute = match.groups()
    try:
        return datetime(int(year or (reference.year if reference else now.year)), int(month), int(day), int(hour), int(minute), tzinfo=JST)
    except ValueError:
        return None


def _integer(text: str) -> int:
    values = re.findall(r"[\d,]+", text or "")
    return int(values[-1].replace(",", "")) if values else 0


def _element_by_params(element, module: str, link: str):
    matches = element.find_elements(By.CSS_SELECTOR, f'[data-cl-params*="_cl_vmodule:{module};"][data-cl-params*="_cl_link:{link};"]')
    return matches[0] if matches else None


def _posted(elements, reference=None):
    for element in elements:
        for candidate in (element.get_attribute("datetime"), element.get_attribute("title"), element.text):
            parsed = parse_yahoo_datetime(candidate or "", reference)
            if parsed:
                return parsed.isoformat()
    return None


def _general_comment(wrapper, index: int, published_at=None):
    time_link = _element_by_params(wrapper, "cmt_usr", "prmtime")
    if time_link is None:
        return None, 0
    try:
        article = time_link.find_element(By.XPATH, "ancestor::article[1]")
        text = clean_text("\n".join(p.text for p in article.find_elements(By.CSS_SELECTOR, "p") if p.text))
        if not text:
            return None, 0
        href = time_link.get_attribute("href") or ""
        comment_id = href.rstrip("/").rsplit("/", 1)[-1] or hashlib.sha256(text.encode()).hexdigest()[:20]
        empathy = _element_by_params(article, "cmt_usr", "agbtn1")
        reply = _element_by_params(article, "cmt_usr", "opnre")
        reply_count = _integer(reply.text) if reply else 0
        return ({
            "comment_id": comment_id, "comment_type": "general", "parent_comment_id": None,
            "text": text, "posted_at": _posted([time_link, *article.find_elements(By.CSS_SELECTOR, "time")], published_at),
            "empathy_count": _integer(empathy.text) if empathy else None,
            "reply_count": reply_count, "order_index": index,
        }, reply_count)
    except (NoSuchElementException, StaleElementReferenceException):
        return None, 0


def _expert_comments(driver, start_index: int, published_at=None) -> list[dict]:
    comments, seen = [], set()
    anchors = driver.find_elements(By.CSS_SELECTOR, '[data-cl-params*="_cl_vmodule:cmt_athr;"][data-cl-params*="_cl_link:profnm;"]')
    for anchor in anchors:
        try:
            article = anchor.find_element(By.XPATH, "ancestor::article[1]")
            text = clean_text("\n".join(p.text for p in article.find_elements(By.CSS_SELECTOR, "p") if p.text))
            if not text or text in seen:
                continue
            seen.add(text)
            empathy = _element_by_params(article, "cmt_athr", "ref")
            comments.append({
                "comment_id": "expert-" + hashlib.sha256(text.encode()).hexdigest()[:16],
                "comment_type": "expert", "parent_comment_id": None, "text": text,
                "posted_at": _posted(article.find_elements(By.CSS_SELECTOR, "time"), published_at),
                "empathy_count": _integer(empathy.text) if empathy else None, "reply_count": 0,
                "order_index": start_index + len(comments),
            })
        except (NoSuchElementException, StaleElementReferenceException):
            continue
    return comments


def _reply_comments(driver, parent: dict, start_index: int) -> list[dict]:
    comments, seen = [], set()
    anchors = driver.find_elements(By.CSS_SELECTOR, '[data-cl-params*="_cl_vmodule:rep;"][data-cl-params*="_cl_link:profnm;"]')
    for anchor in anchors:
        try:
            article = anchor.find_element(By.XPATH, "ancestor::article[1]")
            text = clean_text("\n".join(p.text for p in article.find_elements(By.CSS_SELECTOR, "p") if p.text))
            if not text or text in seen:
                continue
            seen.add(text)
            empathy = _element_by_params(article, "rep", "agbtn1")
            params = empathy.get_attribute("data-cl-params") if empathy else ""
            match = re.search(r"(?:^|;)cmt_id:([^;]+)", params or "")
            comment_id = match.group(1) if match else hashlib.sha256(f"{parent['comment_id']}\0{text}".encode()).hexdigest()[:20]
            comments.append({
                "comment_id": comment_id, "comment_type": "reply", "parent_comment_id": parent["comment_id"],
                "text": text, "posted_at": _posted(article.find_elements(By.CSS_SELECTOR, "time"), parse_yahoo_datetime(parent.get("posted_at") or "")),
                "empathy_count": _integer(empathy.text) if empathy else None, "reply_count": 0,
                "order_index": start_index + len(comments),
            })
        except (NoSuchElementException, StaleElementReferenceException):
            continue
    return comments


def _expand_replies(driver, wrapper, reply_count: int) -> None:
    button = _element_by_params(wrapper, "cmt_usr", "opnre")
    if not button or reply_count <= 0:
        return
    selector = '[data-cl-params*="_cl_vmodule:rep;"]'
    before = len(driver.find_elements(By.CSS_SELECTOR, selector))
    try:
        driver.execute_script("arguments[0].click()", button)
        WebDriverWait(driver, 5).until(lambda d: len(d.find_elements(By.CSS_SELECTOR, selector)) > before)
    except (TimeoutException, StaleElementReferenceException, WebDriverException):
        return
    for _ in range(max(0, math.ceil(reply_count / 10) - 1)):
        buttons = driver.find_elements(By.XPATH, "//*[self::button or self::a][contains(normalize-space(.), '返信をもっと見る')]")
        if not buttons:
            break
        try:
            driver.execute_script("arguments[0].click()", buttons[0])
            time.sleep(.5)
        except WebDriverException:
            break


def _click_more(driver) -> None:
    for element in driver.find_elements(By.XPATH, "//*[self::button or self::a][contains(normalize-space(.), 'もっと見る')]"):
        try:
            driver.execute_script("arguments[0].click()", element)
        except (StaleElementReferenceException, WebDriverException):
            continue


def fetch_yahoo_comments(article_url: str, *, limit: int = 45, include_replies: bool = True,
                         max_pages: int = 50, published_at: datetime | None = None,
                         progress=None) -> list[dict]:
    article_url = validate_yahoo_url(article_url)
    maximum = max(1, int(limit))
    pages = min(max_pages, max(1, math.ceil(maximum / 10)))
    comments, seen = [], set()
    driver = create_driver()
    try:
        for page in range(1, pages + 1):
            url = comments_url(article_url, page)
            if progress:
                progress(f"Yahooコメント {page}/{pages}ページ", page, pages)
            try:
                driver.get(url)
                WebDriverWait(driver, 20).until(lambda d: d.execute_script("return document.readyState") == "complete")
                assert_not_geo_blocked(driver, url)
                WebDriverWait(driver, 20).until(lambda d: d.find_elements(By.CSS_SELECTOR, 'div[id^="viewable_comment_middle_"],#comment-main'))
            except (TimeoutException, WebDriverException) as exc:
                if page == 1:
                    raise CommentFetchError(f"Yahooコメントページを読み込めませんでした。title={driver.title!r} body={body_text(driver, 500)!r}") from exc
                break
            _click_more(driver)
            for expert in (_expert_comments(driver, len(comments), published_at) if page == 1 else []):
                if expert["comment_id"] not in seen and len(comments) < maximum:
                    seen.add(expert["comment_id"]); comments.append(expert)
            added = 0
            for marker in driver.find_elements(By.CSS_SELECTOR, 'div[id^="viewable_comment_middle_"]'):
                if len(comments) >= maximum:
                    break
                try:
                    wrapper = marker.find_element(By.XPATH, "..")
                except (NoSuchElementException, StaleElementReferenceException):
                    continue
                parent, reply_count = _general_comment(wrapper, len(comments), published_at)
                if not parent or parent["comment_id"] in seen:
                    continue
                seen.add(parent["comment_id"]); comments.append(parent); added += 1
                if include_replies and reply_count and len(comments) < maximum:
                    _expand_replies(driver, wrapper, reply_count)
                    for reply in _reply_comments(driver, parent, len(comments)):
                        if reply["comment_id"] not in seen and len(comments) < maximum:
                            seen.add(reply["comment_id"]); comments.append(reply)
            if not added:
                break
    finally:
        driver.quit()
    return comments
