"""The single normalized job posting table."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # where it came from
    source: Mapped[str] = mapped_column(String(32), index=True)
    source_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # what it is
    title: Mapped[str] = mapped_column(String(500), index=True)
    company: Mapped[str] = mapped_column(String(300), index=True)

    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # normalized 시/도 bucket used by the region filter (서울, 경기, ... 전국)
    location_region: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    salary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # the source's own salary bucket id (Saramin salary.code), kept for filtering later
    salary_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # best-effort annual figure in 만원, used only for sorting; NULL when unknown
    salary_value: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    employment_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    experience: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    education: Mapped[str | None] = mapped_column(String(64), nullable=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1000))

    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    # dedup key - see app/services/dedup_service.py
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    # the posting's OWN keywords, as published by the source (Saramin: job.keyword)
    keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # the search term(s) that surfaced this job here - drives /api/jobs?keyword=
    matched_keywords: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # 0 = the source says the posting is closed
    is_active: Mapped[bool] = mapped_column(Integer, default=1)

    # True when the row came from MockJobCollector (development data, not a real posting)
    is_mock: Mapped[bool] = mapped_column(Integer, default=0)

    __table_args__ = (Index("ix_jobs_source_sourcejobid", "source", "source_job_id"),)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Job {self.source}:{self.source_job_id} {self.title!r}>"
