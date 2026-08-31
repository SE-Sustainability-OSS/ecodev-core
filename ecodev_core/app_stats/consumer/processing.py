"""
Retrievers that return DataFrames from consumer tables for downstream aggregation.
"""
from datetime import datetime

import pandas as pd
from sqlmodel import col
from sqlmodel import select
from sqlmodel import Session

from ecodev_core.app_stats.consumer.tables import RemoteAppProject
from ecodev_core.app_stats.consumer.tables import RemoteHourlyActivity

_ACTIVITY_COLS = [
    'application', 'hour', 'user_email', 'method', 'activity_count', 'ingested_at',
]
_PROJECT_COLS = [
    'application', 'project_id', 'name', 'creator',
    'created_at', 'modified_at', 'description', 'client', 'project_type',
]


def get_activities_df(
        session: Session,
        application: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
) -> pd.DataFrame:
    """
    Returns a DataFrame of remote activity rows, optionally filtered.
    Columns: application, hour, user_email, method, activity_count, ingested_at.
    """
    stmt = select(RemoteHourlyActivity)
    if application is not None:
        stmt = stmt.where(col(RemoteHourlyActivity.application) == application)
    if from_date is not None:
        stmt = stmt.where(col(RemoteHourlyActivity.hour) >= from_date)
    if to_date is not None:
        stmt = stmt.where(col(RemoteHourlyActivity.hour) < to_date)

    rows = session.exec(stmt).all()
    if not rows:
        return pd.DataFrame(columns=_ACTIVITY_COLS)

    return pd.DataFrame(
        [
            {
                'application': r.application,
                'hour': r.hour,
                'user_email': r.user_email,
                'method': r.method,
                'activity_count': r.activity_count,
                'ingested_at': r.ingested_at,
            }
            for r in rows
        ]
    )


def get_projects_df(
        session: Session,
        application: str | None = None,
) -> pd.DataFrame:
    """
    Returns a DataFrame of remote project rows.
    Columns: application, project_id, name, creator, created_at, modified_at,
             description, client, project_type.
    """
    stmt = select(RemoteAppProject)
    if application is not None:
        stmt = stmt.where(col(RemoteAppProject.application) == application)

    rows = session.exec(stmt).all()
    if not rows:
        return pd.DataFrame(columns=_PROJECT_COLS)

    return pd.DataFrame(
        [
            {
                'application': r.application,
                'project_id': r.project_id,
                'name': r.name,
                'creator': r.creator,
                'created_at': r.created_at,
                'modified_at': r.modified_at,
                'description': r.description,
                'client': r.client,
                'project_type': r.project_type,
            }
            for r in rows
        ]
    )
