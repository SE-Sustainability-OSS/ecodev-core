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
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse
from ecodev_core.app_stats.contract import ProjectExport
from ecodev_core.app_stats.contract import ProjectStatsAdapter
from ecodev_core.db_connection import get_session
from ecodev_core.logger import logger_get

log = logger_get(__name__)
_ACTIVITIES_TAG = 'App Stats'


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
    router = APIRouter(prefix=prefix, tags=[_ACTIVITIES_TAG],
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
        log.info('[stats-producer] /activities  from_date=%s  to_date=%s  method=%s  page_size=%d',
                 from_date, to_date, method, page_size)
        t0 = time.monotonic()
        result = get_activities(
            session=session,
            from_date=from_date,
            to_date=to_date,
            method=method,
            page_size=page_size,
        )
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        first_hour = result.items[0].hour if result.items else None
        last_hour = result.items[-1].hour if result.items else None
        log.info('[stats-producer] /activities  returned=%d  first_hour=%s  last_hour=%s'
                 '  next_from_date=%s  elapsed_ms=%d',
                 len(result.items), first_hour, last_hour, result.next_from_date, elapsed_ms)
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
        log.info('[stats-producer] /projects  from_date=%s  to_date=%s', from_date, to_date)
        t0 = time.monotonic()
        items = list(adapter.list_projects(session, from_date, to_date))
        paged = [items[i:i + adapter.page_size]
                 for i in range(0, len(items), adapter.page_size)]

        if not items:
            log.info('[stats-producer] /projects  returned=0  elapsed_ms=%d',
                     round((time.monotonic() - t0) * 1000))
            return PagedResponse(items=[], next_from_date=None)

        page_items = paged[0]
        next_from_date = (
            page_items[-1].created_at
            if len(paged) > 1 and page_items
            else None
        )
        elapsed_ms = round((time.monotonic() - t0) * 1000)
        log.info('[stats-producer] /projects  total=%d  page=%d  next_from_date=%s  elapsed_ms=%d',
                 len(items), len(page_items), next_from_date, elapsed_ms)
        return PagedResponse(items=page_items, next_from_date=next_from_date)
