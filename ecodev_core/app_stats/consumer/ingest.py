"""
Insertors and deletors for remotely ingested stats data.
The lookback-delete-then-upsert pattern prevents stale rows from accumulating
when a producer back-fills or corrects historical data.

`granularity` must be the same value used in the fetch call so the delete scope
matches the ingest scope exactly (idempotent re-runs).
"""
from datetime import datetime

from sqlmodel import col
from sqlmodel import delete
from sqlmodel import Session

from ecodev_core.app_stats.consumer.tables import RemoteActivity
from ecodev_core.app_stats.consumer.tables import RemoteAppProject
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import ProjectExport


def delete_lookback_activities(
        session: Session,
        application: str,
        from_date: datetime,
        granularity: str = 'hour',
) -> None:
    """
    Deletes all `RemoteActivity` rows for `application` and `granularity` at or after `from_date`.
    Call before upserting the new batch to avoid stale rows from prior ingest runs.
    """
    session.exec(
        delete(RemoteActivity)
        .where(col(RemoteActivity.application) == application)
        .where(col(RemoteActivity.granularity) == granularity)
        .where(col(RemoteActivity.period_start) >= from_date)
    )
    session.commit()


def delete_lookback_projects(
        session: Session,
        application: str,
) -> None:
    """
    Deletes all remote project rows for `application`.
    Projects are small enough to replace wholesale each ingest cycle.
    """
    session.exec(
        delete(RemoteAppProject)
        .where(col(RemoteAppProject.application) == application)
    )
    session.commit()


def upsert_remote_activities(
        session: Session,
        application: str,
        activities: list[ActivityExport],
        granularity: str = 'hour',
) -> None:
    """
    Inserts remote activity rows.  Call after `delete_lookback_activities` to avoid duplicates.
    """
    ingested_at = datetime.utcnow()
    session.add_all([
        RemoteActivity(
            application=application,
            granularity=granularity,
            period_start=item.period_start,
            method=item.method,
            activity_count=item.activity_count,
            unique_users=item.unique_users,
            ingested_at=ingested_at,
        )
        for item in activities
    ])
    session.commit()


def upsert_remote_projects(
        session: Session,
        application: str,
        projects: list[ProjectExport],
) -> None:
    """
    Replaces remote project rows.  Call after `delete_lookback_projects`.
    """
    ingested_at = datetime.utcnow()
    session.add_all([
        RemoteAppProject(
            application=application,
            project_id=item.project_id,
            name=item.name,
            creator=item.creator,
            created_at=item.created_at,
            modified_at=item.modified_at,
            description=item.description,
            client=item.client,
            project_type=item.project_type,
            ingested_at=ingested_at,
        )
        for item in projects
    ])
    session.commit()
