"""
Router factory for the /stats producer endpoints.
/stats/activities is always registered.
/stats/projects is only registered when a ProjectStatsAdapter is supplied.
"""
import time
from datetime import datetime
from typing import Callable

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlmodel import Session

from ecodev_core.app_stats.activity_export import get_activities
from ecodev_core.app_stats.api_key import api_key_or_monitoring
from ecodev_core.app_stats.constants import ACTIVITIES_TAG
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse
from ecodev_core.app_stats.contract import ProjectExport
from ecodev_core.app_stats.contract import ProjectStatsAdapter
from ecodev_core.db_connection import get_session
from ecodev_core.logger import logger_get

log = logger_get(__name__)


def get_stats_router(
        prefix: str = '/stats',
        adapter: ProjectStatsAdapter | None = None,
        dependency: Callable = api_key_or_monitoring,
) -> APIRouter:
    """
    Returns a FastAPI router with stats endpoints.

    When `adapter` is None, only /activities is registered (activities-only producer).
    When `adapter` is provided, /projects is also registered.

    Args:
        prefix: URL prefix for all routes (default /stats).
        adapter: App-supplied callable bundle for project retrieval.
        dependency: Auth dependency (default api_key_or_monitoring).
    """
    router = APIRouter(prefix=prefix, tags=[ACTIVITIES_TAG],
                       dependencies=[Depends(dependency)])

    @router.get('/activities', response_model=PagedResponse[ActivityExport])
    def activities_endpoint(
            from_date: datetime | None = Query(default=None),
            to_date: datetime | None = Query(default=None),
            method: str | None = Query(default=None),
            page_size: int = Query(default=500, ge=1, le=5000),
            session: Session = Depends(get_session),
    ) -> PagedResponse[ActivityExport]:
        """
        Returns a page of hourly activity buckets, ordered ascending by hour.
        Pass `next_from_date` from the previous response as `from_date` to advance the cursor.
        """
        result = get_activities(
            session=session,
            from_date=from_date,
            to_date=to_date,
            method=method,
            page_size=page_size,
        )
        return result

    if adapter is not None:
        _register_projects(router, adapter)

    return router


def _register_projects(router: APIRouter, adapter: ProjectStatsAdapter) -> None:
    """
    Registers the /projects endpoint on `router` using the provided adapter.
    """
    @router.get('/projects', response_model=PagedResponse[ProjectExport])
    def projects_endpoint(
            from_date: datetime | None = Query(default=None),
            to_date: datetime | None = Query(default=None),
            session: Session = Depends(get_session),
    ) -> PagedResponse[ProjectExport]:
        """
        Returns a page of project snapshots.
        Registered only when the app supplies a ProjectStatsAdapter.
        """
        items = list(adapter.list_projects(session, from_date, to_date))
        paged = [items[i:i + adapter.page_size]
                 for i in range(0, len(items), adapter.page_size)]

        if not items:
            return PagedResponse(items=[], next_from_date=None)

        page_items = paged[0]
        next_from_date = (
            page_items[-1].created_at
            if len(paged) > 1 and page_items
            else None
        )
        return PagedResponse(items=page_items, next_from_date=next_from_date)
