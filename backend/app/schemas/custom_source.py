"""Request / response shapes for user-added job sites."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.job import JobOut

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")
RESERVED_NAMES = {
    "saramin", "jobkorea", "wanted", "work24", "incruit", "jumpit",
    "albamon", "alba", "indeed", "career", "jobplanet", "rocketpunch", "mock",
}


class CustomSourceBase(BaseModel):
    label: str = Field(min_length=1, max_length=64, description="화면에 표시할 이름")
    site_url: str | None = None
    search_url: str = Field(description="{keyword} 를 포함해야 합니다")
    kind: str = Field(default="html", description="html | json")

    item_selector: str = Field(min_length=1, description="공고 하나를 감싸는 CSS 선택자 또는 JSON 경로")
    title_selector: str | None = None
    company_selector: str | None = None
    location_selector: str | None = None
    salary_selector: str | None = None
    date_selector: str | None = None
    description_selector: str | None = None
    link_selector: str | None = None
    link_template: str | None = None

    enabled: bool = True

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, value: str) -> str:
        if value not in ("html", "json"):
            raise ValueError("kind must be 'html' or 'json'")
        return value

    @field_validator("search_url")
    @classmethod
    def _has_placeholder(cls, value: str) -> str:
        if "{keyword}" not in value:
            raise ValueError("search_url must contain {keyword}")
        return value.strip()


class CustomSourceCreate(CustomSourceBase):
    name: str = Field(description="영문 소문자 slug (예: mysite)")

    @field_validator("name")
    @classmethod
    def _valid_name(cls, value: str) -> str:
        value = value.strip().lower()
        if not NAME_PATTERN.match(value):
            raise ValueError("name must be 2-32 chars: lowercase letters, digits, '-' or '_'")
        if value in RESERVED_NAMES:
            raise ValueError(f"'{value}' is a built-in source name")
        return value


class CustomSourceUpdate(BaseModel):
    """Every field optional - only what is sent gets changed."""

    label: str | None = None
    site_url: str | None = None
    search_url: str | None = None
    kind: str | None = None
    item_selector: str | None = None
    title_selector: str | None = None
    company_selector: str | None = None
    location_selector: str | None = None
    salary_selector: str | None = None
    date_selector: str | None = None
    description_selector: str | None = None
    link_selector: str | None = None
    link_template: str | None = None
    enabled: bool | None = None


class CustomSourceOut(CustomSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CustomSourceTestRequest(CustomSourceBase):
    """Dry run: fetch and parse without saving anything."""

    name: str = "preview"
    keyword: str = "베트남어"


class CustomSourceTestResponse(BaseModel):
    ok: bool
    status: str
    message: str | None = None
    requested_url: str | None = None
    items_found: int = 0
    jobs_parsed: int = 0
    jobs: list[JobOut] = Field(default_factory=list)
