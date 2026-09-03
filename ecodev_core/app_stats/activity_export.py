"""
Retriever that aggregates AppActivity into hourly ActivityExport rows with cursor paging.
"""
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlmodel import col
from sqlmodel import func
from sqlmodel import select
from sqlmodel import Session
from sqlmodel import text

from ecodev_core.app_activity import AppActivity
from ecodev_core.app_stats.constants import DEFAULT_PAGE_SIZE
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse


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

    `next_from_date` is always the first hour NOT yet emitted so the next request with
    `from_date=next_from_date` picks up exactly where this page ended without re-fetching
    any row.  If a single hour exceeds `page_size`, all rows for that hour are emitted and
    `next_from_date` is set to `hour + 1h` to guarantee forward progress.
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

    if len(rows) <= page_size:
        return PagedResponse(
            items=[_to_export(r) for r in rows],
            next_from_date=None,
        )

    # More data exists; determine safe cursor that avoids re-fetching any row.
    page_rows = rows[:page_size]
    overflow_hour = rows[page_size].hour
    last_emitted_hour = page_rows[-1].hour

    if overflow_hour == last_emitted_hour:
        # Degenerate: a single hour holds more than page_size rows.
        # Emit this page as-is and jump the cursor past the entire hour.
        next_from_date = last_emitted_hour + timedelta(hours=1)
    else:
        # Trim current page to complete hours so cursor == first hour not yet seen.
        page_rows = [r for r in page_rows if r.hour < overflow_hour]
        next_from_date = overflow_hour

    return PagedResponse(
        items=[_to_export(r) for r in page_rows],
        next_from_date=next_from_date,
    )


def _to_export(r) -> ActivityExport:
    """Converts one ORM row to an ActivityExport instance."""
    return ActivityExport(
        application=r.application,
        hour=r.hour,
        user_email=r.user_email,
        method=r.method,
        activity_count=r.activity_count,
    )


def _normalize_utc(dt: datetime) -> datetime:
    """
    Strips tzinfo from an aware datetime so Postgres comparisons against naive `created_at` work.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
