from __future__ import annotations

import platform
import re
import shutil
import subprocess
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service

from ...core.exceptions import YahooGeoBlockedError
from ...storage.files import clean_text

GEO_MARKERS = (
    "Yahoo! JAPANは欧州経済領域（EEA）およびイギリスからご利用いただけません",
    "サービスをご利用いただけません",
)


def find_chrome_binary() -> str:
    command = next((shutil.which(name) for name in (
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"
    ) if shutil.which(name)), None)
    if command:
        return command
    candidates: list[Path] = []
    system = platform.system()
    if system == "Darwin":
        candidates = [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ]
    elif system == "Windows":
        import os
        for base in (os.getenv("PROGRAMFILES"), os.getenv("PROGRAMFILES(X86)"), os.getenv("LOCALAPPDATA")):
            if base:
                candidates.append(Path(base) / "Google/Chrome/Application/chrome.exe")
    for path in candidates:
        if path.exists():
            return str(path)
    raise RuntimeError("Chrome / Chromium が見つかりません。")


def browser_user_agent() -> str:
    chrome = find_chrome_binary()
    try:
        version = subprocess.check_output([chrome, "--version"], text=True, stderr=subprocess.DEVNULL)
        major = (re.search(r"(\d+)\.", version) or [None, "140"])[1]
    except Exception:
        major = "140"
    return f"Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36"


def create_driver(*, page_timeout: int = 20):
    options = webdriver.ChromeOptions()
    options.binary_location = find_chrome_binary()
    for argument in (
        "--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
        "--window-size=1400,2200", "--lang=ja-JP", "--disable-extensions",
        "--blink-settings=imagesEnabled=false", "--disable-blink-features=AutomationControlled",
        f"--user-agent={browser_user_agent()}",
    ):
        options.add_argument(argument)
    driver_path = shutil.which("chromedriver")
    try:
        driver = webdriver.Chrome(service=Service(driver_path) if driver_path else Service(), options=options)
        driver.set_page_load_timeout(page_timeout)
        return driver
    except WebDriverException as exc:
        raise RuntimeError(f"Chrome / Selenium の起動に失敗しました: {exc}") from exc


def body_text(driver, limit: int = 8000) -> str:
    try:
        return clean_text(driver.find_element("tag name", "body").text)[:limit]
    except Exception:
        return ""


def assert_not_geo_blocked(driver, url: str) -> None:
    text = clean_text(driver.title) + "\n" + body_text(driver)
    if any(marker in text for marker in GEO_MARKERS):
        raise YahooGeoBlockedError(f"Yahoo! JAPANの地域制限ページが返されました: {url}")

