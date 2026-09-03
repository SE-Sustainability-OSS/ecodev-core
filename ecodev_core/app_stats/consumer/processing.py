"""
Retrievers that return dicts from consumer tables for downstream aggregation.
Callers can convert to a DataFrame via pd.DataFrame(get_remote_activities(...)).
"""
from datetime import datetime

from sqlmodel import col
from sqlmodel import select
from sqlmodel import Session

from ecodev_core.app_stats.consumer.tables import RemoteActivity
from ecodev_core.app_stats.consumer.tables import RemoteAppProject
from ecodev_core.app_stats.constants import HOUR_GRAIN


def get_remote_activities(
        session: Session,
        application: str | None = None,
        granularity: str = HOUR_GRAIN,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
) -> list[dict]:
    """
    Returns remote activity rows as dicts, optionally filtered by application, granularity
    and date range.  Callers can wrap the result with pd.DataFrame(...).
    """
    stmt = select(RemoteActivity).where(col(RemoteActivity.granularity) == granularity)
    if application is not None:
        stmt = stmt.where(col(RemoteActivity.application) == application)
    if from_date is not None:
        stmt = stmt.where(col(RemoteActivity.period_start) >= from_date)
    if to_date is not None:
        stmt = stmt.where(col(RemoteActivity.period_start) < to_date)
    return [row.model_dump() for row in session.exec(stmt).all()]


def get_remote_projects(
        session: Session,
        application: str | None = None,
) -> list[dict]:
    """
    Returns remote project rows as dicts, optionally filtered by application.
    """
    stmt = select(RemoteAppProject)
    if application is not None:
        stmt = stmt.where(col(RemoteAppProject.application) == application)
    return [row.model_dump() for row in session.exec(stmt).all()]
