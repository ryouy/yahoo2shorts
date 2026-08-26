from __future__ import annotations

import json
import time
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError

from ..core.exceptions import OpenAIServiceError
from ..core.security import secret_store


def error_message(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return "OpenAI APIキーが無効です。"
    if isinstance(exc, RateLimitError):
        return "OpenAI APIのレート制限に達しました。しばらく待って再試行してください。"
    if isinstance(exc, APITimeoutError):
        return "OpenAI APIがタイムアウトしました。"
    if isinstance(exc, APIConnectionError):
        return "OpenAI APIへ接続できません。ネットワークを確認してください。"
    if isinstance(exc, APIStatusError):
        return f"OpenAI APIエラー（HTTP {exc.status_code}）"
    return f"OpenAI処理に失敗しました: {exc}"


class OpenAIService:
    def client(self) -> OpenAI:
        key = secret_store.get()
        if not key:
            raise OpenAIServiceError("OpenAI APIキーが未登録です。設定画面から登録してください。")
        return OpenAI(api_key=key, timeout=60, max_retries=0)

    def test_connection(self, model: str) -> dict:
        try:
            client = self.client()
            models = client.models.list()
            available = any(item.id == model for item in models.data)
            return {"ok": True, "model": model, "model_available": available}
        except Exception as exc:
            raise OpenAIServiceError(error_message(exc)) from exc

    def structured(self, *, model: str, instructions: str, prompt: str, schema_name: str,
                   schema: dict, max_output_tokens: int = 4000, retries: int = 3) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                response = self.client().responses.create(
                    model=model,
                    instructions=instructions,
                    input=prompt,
                    text={"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}},
                    max_output_tokens=max_output_tokens,
                    store=False,
                )
                return json.loads(response.output_text)
            except (AuthenticationError, APIConnectionError, APITimeoutError, RateLimitError, APIStatusError, json.JSONDecodeError) as exc:
                last_error = exc
                if isinstance(exc, AuthenticationError):
                    break
                if attempt < retries - 1:
                    time.sleep(min(8, 2 ** (attempt + 1)))
        assert last_error is not None
        raise OpenAIServiceError(error_message(last_error)) from last_error


openai_service = OpenAIService()

