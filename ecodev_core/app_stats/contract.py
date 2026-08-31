"""
Pydantic contract models shared between producers and the opt-in consumer.
"""
from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from typing import Callable
from typing import Generic
from typing import Iterable
from typing import TypeVar

from sqlmodel import Session

from ecodev_core.pydantic_utils import CustomFrozen
from ecodev_core.pydantic_utils import OrmFrozen

T = TypeVar('T')


class ActivityExport(OrmFrozen):
    """
    One hour-bucketed row of app activity, aggregated by (application, hour, user, method).
    `hour` is always UTC-midnight-aligned to the start of the hour.
    """
    application: str
    hour: datetime
    user_email: str
    method: str = ''
    activity_count: int


class ProjectExport(OrmFrozen):
    """
    Snapshot of a project as seen by the stats API.
    `project_id` is the stable, app-local identifier (primary key or slug).
    `project_type` is app-specific (e.g. pcf_only / cft_only / both for cf-tool).
    """
    project_id: str
    name: str | None = None
    creator: str | None = None
    created_at: datetime | None = None
    modified_at: datetime | None = None
    description: str | None = None
    client: str | None = None
    project_type: str | None = None


class PagedResponse(CustomFrozen, Generic[T]):
    """
    Envelope for paginated API responses.
    `next_from_date` is null on the last page; pass it back as `from_date` to fetch the next page.
    """
    items: list[T]
    next_from_date: datetime | None = None


@dataclass
class ProjectStatsAdapter:
    """
    App-supplied adapter that tells the stats router how to retrieve projects.
    Mirrors the Insertor idiom: a dataclass of callables so each app can wire its own ORM layer.
    """
    list_projects: Callable[[Session, datetime | None, datetime | None], Iterable[ProjectExport]]
    page_size: int = field(default=500)
