"""
SQLModel tables for storing remotely ingested stats data.
These tables are intentionally not imported by any __init__.py at or above app_stats/,
so they are never created in producer-only databases.
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field
from sqlmodel import SQLModel


class RemoteActivity(SQLModel, table=True):  # type: ignore
    """
    One time-bucketed row of activity ingested from a remote producer app.

    Keyed on (application, granularity, period_start, method).
    `granularity` is 'hour' or 'month', matching the ActivityExport wire format.
    `unique_users` is pre-aggregated server-side — no user identity is stored here.
    `ingested_at` records when the row was last written, for debugging.
    """
    __tablename__ = 'remote_activity'

    id: Optional[int] = Field(default=None, primary_key=True)
    application: str = Field(index=True)
    granularity: str = Field(index=True)
    period_start: datetime = Field(index=True)
    method: str = Field(default='', index=True)
    activity_count: int
    unique_users: int
    ingested_at: datetime = Field(default_factory=datetime.utcnow)


class RemoteAppProject(SQLModel, table=True):  # type: ignore
    """
    Project snapshot ingested from a remote producer app.
    Unique on (application, project_id).
    """
    __tablename__ = 'remote_app_project'

    id: Optional[int] = Field(default=None, primary_key=True)
    application: str = Field(index=True)
    project_id: str = Field(index=True)
    name: Optional[str] = None
    creator: Optional[str] = None
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    description: Optional[str] = None
    client: Optional[str] = None
    project_type: Optional[str] = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
