"""A job site the user added by hand, stored as configuration rather than code."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomSource(Base):
    __tablename__ = "custom_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # slug
    label: Mapped[str] = mapped_column(String(64))
    site_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # must contain {keyword}
    search_url: Mapped[str] = mapped_column(String(1000))
    # "html" -> CSS selectors, "json" -> dotted paths
    kind: Mapped[str] = mapped_column(String(8), default="html")

    # where one posting lives (CSS selector, or dotted path to a JSON list)
    item_selector: Mapped[str] = mapped_column(String(300))

    title_selector: Mapped[str | None] = mapped_column(String(300), nullable=True)
    company_selector: Mapped[str | None] = mapped_column(String(300), nullable=True)
    location_selector: Mapped[str | None] = mapped_column(String(300), nullable=True)
    salary_selector: Mapped[str | None] = mapped_column(String(300), nullable=True)
    date_selector: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description_selector: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # html: selector for the <a>; json: path to the url/id value
    link_selector: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # optional template to build a URL out of the link value, e.g.
    # "https://example.com/jobs/{value}"
    link_template: Mapped[str | None] = mapped_column(String(500), nullable=True)

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CustomSource {self.name} ({self.kind})>"
