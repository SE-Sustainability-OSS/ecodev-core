"""
Retriever that aggregates AppActivity into time-bucketed ActivityExport rows with cursor paging.
"""
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from sqlmodel import col
from sqlmodel import func
from sqlmodel import select
from sqlmodel import Session

from ecodev_core.app_activity import AppActivity
from ecodev_core.app_stats.constants import DEFAULT_PAGE_SIZE
from ecodev_core.app_stats.constants import HOUR_GRAIN
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse


def get_activities(
        session: Session,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        method: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        granularity: str = HOUR_GRAIN,
) -> PagedResponse[ActivityExport]:
    """
    Returns a page of time-bucketed activity rows, ordered ascending by period_start.

    `granularity` is one of 'hour' (default) or 'month'.
    `unique_users` is computed server-side — user identity is never included in the response.
    Pass `next_from_date` from the previous response as `from_date` to advance the cursor.

    `next_from_date` is always the first bucket NOT yet emitted so the next request picks up
    exactly where this page ended without re-fetching any row.  If a single bucket exceeds
    `page_size`, all rows for that bucket are emitted and `next_from_date` is set to
    `bucket_start + one_period` to guarantee forward progress.
    """
    stmt = (
        select(
            func.coalesce(col(AppActivity.application), '').label('application'),
            func.date_trunc(granularity, col(AppActivity.created_at)).label('period_start'),
            func.coalesce(col(AppActivity.method), '').label('method'),
            func.count().label('activity_count'),
            func.count(func.distinct(col(AppActivity.user))).label('unique_users'),
        )
        .group_by(
            func.coalesce(col(AppActivity.application), ''),
            func.date_trunc(granularity, col(AppActivity.created_at)),
            func.coalesce(col(AppActivity.method), ''),
        )
        .order_by(func.date_trunc(granularity, col(AppActivity.created_at)))
    )

    if from_date is not None:
        stmt = stmt.where(
            func.date_trunc(granularity, col(AppActivity.created_at))
            >= _normalize_utc(from_date)
        )
    if to_date is not None:
        stmt = stmt.where(
            func.date_trunc(granularity, col(AppActivity.created_at))
            < _normalize_utc(to_date)
        )
    if method is not None:
        stmt = stmt.where(col(AppActivity.method) == method)

    stmt = stmt.limit(page_size + 1)
    rows = session.exec(stmt).all()

    if len(rows) <= page_size:
        return PagedResponse(
            items=[_to_export(r, granularity) for r in rows],
            next_from_date=None,
        )

    page_rows = rows[:page_size]
    overflow_period = rows[page_size].period_start
    last_emitted_period = page_rows[-1].period_start

    if overflow_period == last_emitted_period:
        # Degenerate: a single bucket holds more than page_size rows; advance past it.
        next_from_date = last_emitted_period + _one_period(granularity)
    else:
        page_rows = [r for r in page_rows if r.period_start < overflow_period]
        next_from_date = overflow_period

    return PagedResponse(
        items=[_to_export(r, granularity) for r in page_rows],
        next_from_date=next_from_date,
    )


def _to_export(r, granularity: str) -> ActivityExport:
    """Converts one ORM row to an ActivityExport instance."""
    return ActivityExport(
        application=r.application,
        period_start=r.period_start,
        granularity=granularity,
        method=r.method,
        activity_count=r.activity_count,
        unique_users=r.unique_users,
    )


def _one_period(granularity: str) -> timedelta:
    """Returns the forward-advance step for the degenerate cursor case."""
    if granularity == 'month':
        return timedelta(days=32)
    return timedelta(hours=1)


def _normalize_utc(dt: datetime) -> datetime:
    """
    Strips tzinfo from an aware datetime so Postgres comparisons against naive `created_at` work.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
