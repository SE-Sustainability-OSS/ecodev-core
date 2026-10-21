"""
Retrievers that aggregate AppActivity into time-bucketed export rows with cursor paging.
"""
import hashlib
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from typing import Callable

from sqlalchemy import literal
from sqlmodel import col
from sqlmodel import func
from sqlmodel import select
from sqlmodel import Session

from ecodev_core.app_activity import AppActivity
from ecodev_core.app_stats.constants import DAY_GRAIN
from ecodev_core.app_stats.constants import DEFAULT_PAGE_SIZE
from ecodev_core.app_stats.constants import HOUR_GRAIN
from ecodev_core.app_stats.constants import MONTH_GRAIN
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse
from ecodev_core.app_stats.contract import UserActivityExport
from ecodev_core.date_utils import as_utc


def get_activities(
        session: Session,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        method: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        granularity: str = HOUR_GRAIN,
        group_by_method: bool = True,
        group_by_application: bool = True,
) -> PagedResponse[ActivityExport]:
    """
    Returns a page of time-bucketed activity rows, ordered ascending by period_start.

    `granularity` is one of 'hour' (default) or 'month'.
    `unique_users` is computed server-side — user identity is never included in the response.
    Pass `next_from_date` from the previous response as `from_date` to advance the cursor.

    `unique_users` is a distinct count, so it is additive across the returned rows only
    when every dimension a user can span has been collapsed: a user appears once in each
    method row they touched and each application row they touched, so summing a split
    response overstates the total.  Callers that intend to sum it should pass
    `group_by_method=False` and `group_by_application=False`, which collapses the
    corresponding column to '' and emits a single row per period.

    `next_from_date` is always the first bucket NOT yet emitted so the next request picks up
    exactly where this page ended without re-fetching any row.  If a single bucket exceeds
    `page_size`, all rows for that bucket are emitted and `next_from_date` is set to
    `bucket_start + one_period` to guarantee forward progress.
    """
    period = func.date_trunc(granularity, col(AppActivity.created_at))
    application_col = func.coalesce(col(AppActivity.application), '')
    method_col = func.coalesce(col(AppActivity.method), '')

    group_cols = [period]
    if group_by_application:
        group_cols.append(application_col)
    if group_by_method:
        group_cols.append(method_col)

    stmt = (
        select(
            (application_col if group_by_application else literal('')).label('application'),
            period.label('period_start'),
            (method_col if group_by_method else literal('')).label('method'),
            func.count().label('activity_count'),
            func.count(func.distinct(col(AppActivity.user))).label('unique_users'),
        )
        .group_by(*group_cols)
        .order_by(period)
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

    rows = _rows_for_page(session, stmt, period, page_size)
    return _paged(rows, page_size, granularity, lambda r: _to_export(r, granularity))


def get_user_activities(
        session: Session,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
) -> PagedResponse[UserActivityExport]:
    """
    Returns a page of one row per (UTC day, application, person), ordered by day.

    The consumer counts distinct `user_key` values over any window and any set of apps,
    so a person active on several days or in several apps is counted once.
    Paging follows the same `next_from_date` cursor as `get_activities`.
    """
    period = func.date_trunc(DAY_GRAIN, col(AppActivity.created_at))
    application_col = func.coalesce(col(AppActivity.application), '')
    stmt = (
        select(
            application_col.label('application'),
            period.label('period_start'),
            col(AppActivity.user).label('user'),
            func.count().label('activity_count'),
        )
        .where(col(AppActivity.user).is_not(None))
        .group_by(period, application_col, col(AppActivity.user))
        .order_by(period)
    )
    if from_date is not None:
        stmt = stmt.where(period >= _normalize_utc(from_date))
    if to_date is not None:
        stmt = stmt.where(period < _normalize_utc(to_date))

    rows = _rows_for_page(session, stmt, period, page_size)
    return _paged(rows, page_size, DAY_GRAIN, _to_user_export)


def user_key(user: str) -> str:
    """
    Pseudonymous key shared by every app for the same login.
    """
    return hashlib.sha256(user.strip().lower().encode()).hexdigest()


def _rows_for_page(session: Session, statement, period, page_size: int) -> list:
    """
    One page of period-ordered rows, with a split bucket completed.

    NOTE: The first read stops at page_size plus one. When that extra row is still
    inside the last bucket, a second read loads the whole bucket so none of its
    rows are dropped when the cursor moves on.
    """
    rows = list(session.exec(statement.limit(page_size + 1)).all())
    if len(rows) <= page_size:
        return rows
    if rows[page_size].period_start != rows[page_size - 1].period_start:
        return rows
    bucket = rows[page_size - 1].period_start
    complete = list(session.exec(statement.where(period == bucket)).all())
    held = [row for row in rows if row.period_start == bucket]
    if len(complete) < len(held):
        return rows
    earlier = [row for row in rows if row.period_start < bucket]
    return earlier + complete


def _paged(rows: list, page_size: int, granularity: str, convert: Callable) -> PagedResponse:
    """
    Cuts one page of period-ordered rows without splitting a bucket across pages.

    `next_from_date` is the first bucket not yet emitted. When one bucket alone exceeds
    `page_size`, every row of that bucket is emitted and the cursor moves to the next
    bucket. That page can be larger than `page_size`.
    """
    if len(rows) <= page_size:
        return PagedResponse(items=[convert(r) for r in rows], next_from_date=None)

    page_rows = rows[:page_size]
    overflow_period = rows[page_size].period_start
    last_emitted_period = page_rows[-1].period_start
    if overflow_period == last_emitted_period:
        return PagedResponse(
            items=[convert(row) for row in rows],
            next_from_date=_next_period_start(overflow_period, granularity),
        )
    return PagedResponse(
        items=[convert(row) for row in page_rows if row.period_start < overflow_period],
        next_from_date=overflow_period,
    )


def _to_user_export(r) -> UserActivityExport:
    """
    Converts one grouped row to a UserActivityExport, hashing the login.
    """
    return UserActivityExport(
        user_key=user_key(r.user),
        application=r.application,
        period_start=as_utc(r.period_start),
        activity_count=r.activity_count,
    )


def _to_export(r, granularity: str) -> ActivityExport:
    """
    Converts one ORM row to an ActivityExport instance.
    """
    return ActivityExport(
        application=r.application,
        period_start=as_utc(r.period_start),
        granularity=granularity,
        method=r.method,
        activity_count=r.activity_count,
        unique_users=r.unique_users,
    )


def _next_period_start(period_start: datetime, granularity: str) -> datetime:
    """
    Returns the start of the bucket following period_start so an oversized bucket
    advances the cursor to the next clean bucket boundary without skipping it.
    """
    if granularity == MONTH_GRAIN:
        return (period_start.replace(day=1) + timedelta(days=31)).replace(day=1)
    if granularity == DAY_GRAIN:
        return period_start + timedelta(days=1)
    return period_start + timedelta(hours=1)


def _normalize_utc(dt: datetime) -> datetime:
    """
    Strips tzinfo from an aware datetime so Postgres comparisons against naive `created_at` work.
    """
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
