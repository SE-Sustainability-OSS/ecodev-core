"""
Router factory for the /stats producer endpoints.
/stats/activities and /stats/users are always registered.
/stats/projects is only registered when a ProjectStatsAdapter is supplied.
"""
from datetime import datetime
from functools import partial
from typing import Callable

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlmodel import Session

from ecodev_core.app_stats.activity_export import get_activities
from ecodev_core.app_stats.activity_export import get_user_activities
from ecodev_core.app_stats.api_key import api_key_auth
from ecodev_core.app_stats.constants import ACTIVITIES_TAG
from ecodev_core.app_stats.constants import HOUR_GRAIN
from ecodev_core.app_stats.constants import MONTH_GRAIN
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse
from ecodev_core.app_stats.contract import ProjectExport
from ecodev_core.app_stats.contract import ProjectStatsAdapter
from ecodev_core.app_stats.contract import UserActivityExport
from ecodev_core.db_connection import get_session


def get_stats_router(
        prefix: str = '/stats',
        adapter: ProjectStatsAdapter | None = None,
        dependency: Callable = api_key_auth,
        included_applications: tuple[str, ...] | None = None,
        application_name: str | None = None,
) -> APIRouter:
    """
    Returns a FastAPI router with stats endpoints.

    /activities and /users are always registered. When `adapter` is provided,
    /projects is registered as well.

    Set `included_applications` and `application_name` together when this process
    shares its activity table. The endpoints then count only those labels and emit
    them as `application_name`, one activity stream for this app.
    """
    owned = _owned_applications(included_applications, application_name)
    router = APIRouter(prefix=prefix, tags=[ACTIVITIES_TAG],
                       dependencies=[Depends(dependency)])
    router.add_api_route(
        '/activities',
        partial(_activities_endpoint, owned, application_name),
        response_model=PagedResponse[ActivityExport],
        methods=['GET'],
    )
    router.add_api_route(
        '/users',
        partial(_users_endpoint, owned, application_name),
        response_model=PagedResponse[UserActivityExport],
        methods=['GET'],
    )
    if adapter is not None:
        router.add_api_route(
            '/projects',
            partial(_projects_endpoint, adapter),
            response_model=list[ProjectExport],
            methods=['GET'],
        )
    return router


def _activities_endpoint(
        included_applications: tuple[str, ...] | None,
        application_name: str | None,
        from_date: datetime | None = Query(default=None),
        to_date: datetime | None = Query(default=None),
        method: str | None = Query(default=None),
        page_size: int = Query(default=500, ge=1, le=5000),
        granularity: str = Query(default=HOUR_GRAIN, pattern=f'^({HOUR_GRAIN}|{MONTH_GRAIN})$'),
        group_by_method: bool = Query(default=True),
        group_by_application: bool = Query(default=True),
        session: Session = Depends(get_session),
) -> PagedResponse[ActivityExport]:
    """
    Returns a page of time-bucketed activity rows, ordered by period_start.

    Pass `next_from_date` back as `from_date`. `granularity=month` pre-aggregates
    `unique_users`. `group_by_method=false` and `group_by_application=false` emit
    one additive row per period. A configured application name ignores
    `group_by_application` and keeps that single name.
    """
    return get_activities(
        session=session,
        from_date=from_date,
        to_date=to_date,
        method=method,
        page_size=page_size,
        granularity=granularity,
        group_by_method=group_by_method,
        group_by_application=group_by_application,
        included_applications=included_applications,
        application_name=application_name,
    )


def _users_endpoint(
        included_applications: tuple[str, ...] | None,
        application_name: str | None,
        from_date: datetime | None = Query(default=None),
        to_date: datetime | None = Query(default=None),
        page_size: int = Query(default=500, ge=1, le=5000),
        session: Session = Depends(get_session),
) -> PagedResponse[UserActivityExport]:
    """
    Returns a page of one row per UTC day, application, and pseudonymous person.

    Pass `next_from_date` back as `from_date`. A configured application name
    collapses the owned labels to one row per person and day.
    """
    return get_user_activities(
        session=session,
        from_date=from_date,
        to_date=to_date,
        page_size=page_size,
        included_applications=included_applications,
        application_name=application_name,
    )


def _owned_applications(
        included_applications: tuple[str, ...] | None,
        application_name: str | None,
) -> tuple[str, ...] | None:
    """
    Validate the shared-table allow-list.

    Both arguments stay unset when the producer owns its activity table. The
    returned labels are the ones the activity queries keep.
    """
    if included_applications is None and application_name is None:
        return None
    owned = tuple(
        label.strip() for label in included_applications or () if label and label.strip()
    )
    if not owned or application_name is None or not application_name.strip():
        raise ValueError('included_applications and application_name must be set together')
    return owned


def _projects_endpoint(
        adapter: ProjectStatsAdapter,
        from_date: datetime | None = Query(default=None),
        to_date: datetime | None = Query(default=None),
        session: Session = Depends(get_session),
) -> list[ProjectExport]:
    """
    Returns all project snapshots from the supplied adapter in a single response.
    """
    return list(adapter.list_projects(session, from_date, to_date))
