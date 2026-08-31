"""
Retriever that aggregates AppActivity into hourly ActivityExport rows with cursor paging.
"""
from datetime import datetime
from datetime import timezone

from sqlmodel import col
from sqlmodel import func
from sqlmodel import select
from sqlmodel import Session
from sqlmodel import text

from ecodev_core.app_activity import AppActivity
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse
from ecodev_core.logger import logger_get

log = logger_get(__name__)
DEFAULT_PAGE_SIZE = 500

_HOUR_TRUNC = text("date_trunc('hour', app_activity.created_at)")


def get_activities(
        session: Session,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        method: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
) -> PagedResponse[ActivityExport]:
    """
    Returns a page of hourly-bucketed activity rows, ordered ascending by hour.
    Pass `next_from_date` from the previous response as `from_date` to get the next page.
    All timestamps are UTC.
    """
    stmt = (
        select(
            func.coalesce(col(AppActivity.application), '').label('application'),
            func.date_trunc('hour', col(AppActivity.created_at)).label('hour'),
            func.coalesce(col(AppActivity.user), '').label('user_email'),
            func.coalesce(col(AppActivity.method), '').label('method'),
            func.count().label('activity_count'),
        )
        .group_by(
            func.coalesce(col(AppActivity.application), ''),
            func.date_trunc('hour', col(AppActivity.created_at)),
            func.coalesce(col(AppActivity.user), ''),
            func.coalesce(col(AppActivity.method), ''),
        )
        .order_by(func.date_trunc('hour', col(AppActivity.created_at)))
    )

    if from_date is not None:
        stmt = stmt.where(
            func.date_trunc('hour', col(AppActivity.created_at)) >= _normalize_utc(from_date)
        )
    if to_date is not None:
        stmt = stmt.where(
            func.date_trunc('hour', col(AppActivity.created_at)) < _normalize_utc(to_date)
        )
    if method is not None:
        stmt = stmt.where(col(AppActivity.method) == method)

    stmt = stmt.limit(page_size + 1)
    rows = session.exec(stmt).all()

    has_more = len(rows) > page_size
    items = [
        ActivityExport(
            application=r.application,
            hour=r.hour,
            user_email=r.user_email,
            method=r.method,
            activity_count=r.activity_count,
        )
        for r in rows[:page_size]
    ]
    next_from_date = rows[page_size - 1].hour if has_more and items else None

    log.info('[activity-export] query window from_date=%s to_date=%s method=%s  '
             'raw_rows=%d  page_items=%d  has_more=%s  next_from_date=%s',
             from_date, to_date, method, len(rows), len(items), has_more, next_from_date)
    return PagedResponse(items=items, next_from_date=next_from_date)


def _normalize_utc(dt: datetime) -> datetime:
    """
    Strips tzinfo from an aware datetime so Postgres comparisons against naive `created_at` work.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
