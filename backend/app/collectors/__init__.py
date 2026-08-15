"""Collector registry.

Adding a new job site comes in two flavours:

* **in code** - write a JobCollector subclass and append it to COLLECTOR_CLASSES;
* **by hand** - add it from the UI, which stores a CustomSource row that
  CustomCollector turns into a working source at runtime.

Nothing else in the app needs to change either way.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors.base import CollectorResult, JobCollector, NormalizedJob, SourceStatus
from app.collectors.custom import CustomCollector
from app.collectors.incruit import IncruitCollector
from app.collectors.jobkorea import JobKoreaCollector
from app.collectors.jobploy import JobployCollector
from app.collectors.jumpit import JumpitCollector
from app.collectors.mock import MockJobCollector
from app.collectors.placeholders import (
    AlbaCollector,
    AlbamonCollector,
    BuddiesKoreaCollector,
    CareerCollector,
    IndeedCollector,
    JobPlanetCollector,
    KoworkCollector,
    KWorkCollector,
    RocketPunchCollector,
)
from app.collectors.saramin import SaraminCollector
from app.collectors.wanted import WantedCollector
from app.collectors.work24 import Work24Collector

COLLECTOR_CLASSES: list[type[JobCollector]] = [
    SaraminCollector,
    JobKoreaCollector,
    WantedCollector,
    Work24Collector,
    IncruitCollector,
    JobployCollector,
    JumpitCollector,
    AlbamonCollector,
    AlbaCollector,
    IndeedCollector,
    CareerCollector,
    JobPlanetCollector,
    KoworkCollector,
    KWorkCollector,
    BuddiesKoreaCollector,
    RocketPunchCollector,
]

# sources ticked by default in the UI
DEFAULT_SOURCES: list[str] = ["saramin", "jobkorea", "wanted", "work24", "incruit", "jobploy"]


def load_custom_sources(db: Session) -> list:
    from app.models.custom_source import CustomSource

    return list(db.scalars(select(CustomSource).order_by(CustomSource.id)))


def build_collectors(db: Session | None = None) -> dict[str, JobCollector]:
    """Built-in collectors, plus any the user added by hand."""
    collectors: dict[str, JobCollector] = {cls.name: cls() for cls in COLLECTOR_CLASSES}
    if db is not None:
        for config in load_custom_sources(db):
            collectors[config.name] = CustomCollector(config)
    return collectors


def get_collector(name: str) -> JobCollector | None:
    for cls in COLLECTOR_CLASSES:
        if cls.name == name:
            return cls()
    return None


__all__ = [
    "COLLECTOR_CLASSES",
    "DEFAULT_SOURCES",
    "CollectorResult",
    "CustomCollector",
    "JobCollector",
    "MockJobCollector",
    "NormalizedJob",
    "SourceStatus",
    "build_collectors",
    "get_collector",
    "load_custom_sources",
]
