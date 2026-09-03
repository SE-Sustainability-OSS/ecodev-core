"""
Insertors and deletors for remotely ingested stats data.

The ingest pattern is: delete, then upsert.  Both the delete and the upsert must
receive the same `from_date` and `granularity` that were passed to `fetch_activities`,
so the delete scope matches the fetch scope exactly and repeated runs replace identical
rows rather than duplicating them (idempotent).
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
    Deletes RemoteActivity rows where application == `application`
    AND granularity == `granularity` AND period_start >= `from_date`.

    Pass the same `from_date` and `granularity` used in the fetch call so the delete scope
    matches the ingest scope exactly, making repeated runs idempotent.
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
    Deletes all RemoteAppProject rows for `application` (full replacement each cycle).
    Projects are not date-partitioned, so the whole set is replaced on every ingest run.
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
