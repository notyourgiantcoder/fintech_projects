from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NewsItem(BaseModel):
    title: str
    source: str | None
    link: str
    published: datetime | None


class Filing(BaseModel):
    form: str
    filed: str
    description: str | None
    url: str


class Story(BaseModel):
    title: str
    url: str | None
    points: int
    comments: int
    created_at: str
    discussion_url: str


class Article(BaseModel):
    url: str
    title: str | None
    text: str
    truncated: bool
