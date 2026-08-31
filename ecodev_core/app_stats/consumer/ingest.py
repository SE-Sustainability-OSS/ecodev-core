"""
Insertors and deletors for remotely ingested stats data.
The lookback-delete-then-upsert pattern prevents stale rows from accumulating
when a producer back-fills or corrects historical data.
"""
from datetime import datetime

from sqlmodel import col
from sqlmodel import delete
from sqlmodel import Session

from ecodev_core.app_stats.consumer.tables import RemoteAppProject
from ecodev_core.app_stats.consumer.tables import RemoteHourlyActivity
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import ProjectExport
from ecodev_core.logger import logger_get

log = logger_get(__name__)


def delete_lookback_activities(
        session: Session,
        application: str,
        from_date: datetime,
) -> None:
    """
    Deletes all remote activity rows for `application` on or after `from_date`.
    Call before upserting the new page to avoid stale per-method duplicates.
    """
    session.exec(
        delete(RemoteHourlyActivity)
        .where(col(RemoteHourlyActivity.application) == application)
        .where(col(RemoteHourlyActivity.hour) >= from_date)
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
) -> None:
    """
    Inserts remote activity rows.  Call after `delete_lookback_activities` to avoid duplicates.
    """
    ingested_at = datetime.utcnow()
    hours = sorted({a.hour for a in activities}) if activities else []
    for item in activities:
        session.add(RemoteHourlyActivity(
            application=application,
            hour=item.hour,
            user_email=item.user_email,
            method=item.method,
            activity_count=item.activity_count,
            ingested_at=ingested_at,
        ))
    session.commit()
    log.info('[consumer-ingest] upserted %d activity rows for %s  '
             'hour_range=[%s, %s]',
             len(activities), application,
             hours[0] if hours else None,
             hours[-1] if hours else None)


def upsert_remote_projects(
        session: Session,
        application: str,
        projects: list[ProjectExport],
) -> None:
    """
    Replaces remote project rows.  Call after `delete_lookback_projects`.
    """
    ingested_at = datetime.utcnow()
    for item in projects:
        session.add(RemoteAppProject(
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
        ))
    session.commit()
    sample = projects[0].name if projects else None
    log.info('[consumer-ingest] upserted %d project rows for %s  sample_name=%s',
             len(projects), application, sample)
