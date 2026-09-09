from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class SettingsUpdate(BaseModel):
    values: dict


class ApiKeyInput(BaseModel):
    api_key: str = Field(min_length=10)


class ProjectCreate(BaseModel):
    mode: Literal["url", "request", "gonline"] = "url"
    request_text: str = ""
    urls: list[str] = Field(default_factory=list)
    article_count: int = Field(default=3, ge=1, le=10)
    video_mode: Literal["normal", "gold"] = "normal"


class DiscoveryRequest(BaseModel):
    mode: Literal["url", "request", "gonline"]
    request_text: str = ""
    urls: list[str] = Field(default_factory=list)
    article_count: int = Field(default=3, ge=1, le=10)


class ArticleApproval(BaseModel):
    article_ids: list[int] = Field(min_length=1)


class Intro(BaseModel):
    headline: str
    explainer: str
    narration: str
    summary_narration: str = ""


class Post(BaseModel):
    text: str
    reply_to: int | None = None
    tone: str = "rough"
    importance: int = Field(default=3, ge=1, le=5)
    source_comment_ids: list[str] = Field(default_factory=list)


class Outro(BaseModel):
    text: str
    narration: str


class ScriptContent(BaseModel):
    title: str
    source: str
    url: str
    youtube_title: str = ""
    youtube_hashtags: list[str] = Field(default_factory=list)
    youtube_summary: str = ""
    intro: Intro
    posts: list[Post] = Field(min_length=1, max_length=20)
    outro: Outro
    estimated_seconds: float | None = None

    @field_validator("posts")
    @classmethod
    def reject_empty_posts(cls, posts: list[Post]) -> list[Post]:
        if any(not post.text.strip() for post in posts):
            raise ValueError("空のコメントは保存できません。")
        return posts

    @model_validator(mode="after")
    def validate_replies(self):
        for index, post in enumerate(self.posts, start=1):
            if post.reply_to is not None and not (1 <= post.reply_to < index):
                raise ValueError(f"レス{index}の返信先が不正です。")
        return self


class ScriptSave(BaseModel):
    script: ScriptContent
