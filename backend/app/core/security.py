from __future__ import annotations

import os
from pathlib import Path

from .config import DATA_DIR

SERVICE_NAME = "YahooShortsStudio"
ACCOUNT_NAME = "openai_api_key"


class SecretStore:
    """OS keychain first, permission-restricted local file as a portable fallback."""

    def __init__(self) -> None:
        self.fallback = DATA_DIR / "secrets" / "openai_api_key"

    def _keyring(self):
        try:
            import keyring

            return keyring
        except Exception:
            return None

    def get(self) -> str | None:
        env_value = os.getenv("OPENAI_API_KEY", "").strip()
        if env_value:
            return env_value
        keyring = self._keyring()
        if keyring:
            try:
                value = keyring.get_password(SERVICE_NAME, ACCOUNT_NAME)
                if value:
                    return value.strip()
            except Exception:
                pass
        try:
            return self.fallback.read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    def set(self, value: str) -> str:
        value = value.strip()
        if not value.startswith("sk-"):
            raise ValueError("OpenAI APIキーの形式が正しくありません。")
        keyring = self._keyring()
        if keyring:
            try:
                keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, value)
                self._delete_fallback()
                return "os_keychain"
            except Exception:
                pass
        self.fallback.parent.mkdir(parents=True, exist_ok=True)
        self.fallback.write_text(value, encoding="utf-8")
        try:
            self.fallback.chmod(0o600)
        except OSError:
            pass
        return "local_secret_file"

    def delete(self) -> None:
        keyring = self._keyring()
        if keyring:
            try:
                keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
            except Exception:
                pass
        self._delete_fallback()

    def _delete_fallback(self) -> None:
        try:
            self.fallback.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def mask(value: str | None) -> str | None:
        if not value:
            return None
        if len(value) < 12:
            return "••••••••"
        return f"{value[:7]}-••••••••-{value[-4:]}"


secret_store = SecretStore()

