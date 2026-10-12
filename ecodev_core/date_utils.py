"""
Module implementing shared datetime helpers
"""
from datetime import datetime
from datetime import timezone


def utc_now() -> datetime:
    """
    Returns a timezone-aware current UTC datetime, as required by SQLModel's \
    datetime column type.

    NOTE: introduced to enforce aware datetime timezone : https://github.com/fastapi/sqlmodel/releases#release-0.0.45
    """
    return datetime.now(timezone.utc)


def as_utc(dt: datetime | None) -> datetime | None:
    """
    Returns `dt` as timezone-aware UTC; naive values are assumed to already be UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
