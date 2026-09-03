"""
Retrievers that return dicts from consumer tables for downstream aggregation.
Callers can convert to a DataFrame via pd.DataFrame(get_remote_activities(...)).
"""
from datetime import datetime

from sqlmodel import col
from sqlmodel import select
from sqlmodel import Session

from ecodev_core.app_stats.consumer.tables import RemoteAppProject
from ecodev_core.app_stats.consumer.tables import RemoteHourlyActivity


def get_remote_activities(
        session: Session,
        application: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
) -> list[dict]:
    """
    Returns remote activity rows as dicts, optionally filtered by application and date range.
    """
    stmt = select(RemoteHourlyActivity)
    if application is not None:
        stmt = stmt.where(col(RemoteHourlyActivity.application) == application)
    if from_date is not None:
        stmt = stmt.where(col(RemoteHourlyActivity.hour) >= from_date)
    if to_date is not None:
        stmt = stmt.where(col(RemoteHourlyActivity.hour) < to_date)
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
