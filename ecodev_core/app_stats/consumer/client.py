"""
HTTP client for polling a remote app's /stats endpoints.
Activities follow `next_from_date` cursors; projects are fetched in a single request.
"""
from datetime import datetime
from http import HTTPStatus
from typing import Any
from typing import Generator
from urllib.parse import quote

import requests
from pydantic import ConfigDict
from pydantic import field_validator

from ecodev_core.app_stats.constants import ACCEPT_HEADER
from ecodev_core.app_stats.constants import ACTIVITIES_PATH
from ecodev_core.app_stats.constants import API_KEY_HEADER
from ecodev_core.app_stats.constants import FROM_DATE
from ecodev_core.app_stats.constants import GRANULARITY
from ecodev_core.app_stats.constants import HOUR_GRAIN
from ecodev_core.app_stats.constants import JSON_MIME
from ecodev_core.app_stats.constants import PROJECTS_PATH
from ecodev_core.app_stats.constants import TO_DATE
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse
from ecodev_core.app_stats.contract import ProjectExport
from ecodev_core.rest_api_client import RestApiClient

# /stats/projects is registered only when a producer supplies a ProjectStatsAdapter,
# so a 404 there is a valid opt-out rather than a failure.
ABSENT_ENDPOINT = (HTTPStatus.NOT_FOUND,)


class StatsApiClient(RestApiClient):
    """
    Client pulling activity and project stats from a remote producer app.

    Attributes:
        base_url: Root URL of the producer app (e.g. http://carbon_footprint_backend:80).
        api_key: Value sent as X-API-Key header.
    """
    model_config = ConfigDict(frozen=True)
    api_key: str

    def fetch_activities(
            self,
            from_date: datetime | None = None,
            to_date: datetime | None = None,
            granularity: str = HOUR_GRAIN,
    ) -> Generator[ActivityExport, None, None]:
        """
        Yields all ActivityExport rows for the given granularity, following pagination.
        Tolerates no error status: /stats/activities is always registered, so any failure
        means the producer is unreachable and must not be mistaken for "no activity".
        """
        yield from _follow_pages(self, ACTIVITIES_PATH, from_date, to_date,
                                 granularity, ActivityExport, tolerate=())

    def fetch_projects(
            self,
            from_date: datetime | None = None,
            to_date: datetime | None = None,
    ) -> list[ProjectExport] | None:
        """
        Returns all ProjectExport rows in a single request, or None when the producer does
        not expose /stats/projects.  None is deliberately distinct from an empty list so
        callers can leave stored rows untouched instead of replacing them with nothing.
        """
        url = _build_url(self.base_url, PROJECTS_PATH, from_date, to_date)
        raw = _get_json(self, url, tolerate=ABSENT_ENDPOINT)
        if raw is None:
            return None
        return [ProjectExport.model_validate(item) for item in raw]

    @field_validator('base_url')
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        """Strips trailing slash and requires http(s) scheme."""
        value = value.rstrip('/')
        if not value.startswith(('http://', 'https://')):
            raise ValueError(f'base_url must start with http:// or https://, got: {value!r}')
        return value

    @field_validator('api_key')
    @classmethod
    def _check_api_key(cls, value: str) -> str:
        """Rejects empty API keys."""
        if not value:
            raise ValueError('api_key must not be empty')
        return value

    def _get_header(self) -> dict:
        return {API_KEY_HEADER: self.api_key, ACCEPT_HEADER: JSON_MIME}


def _build_url(
        base_url: str,
        path: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        granularity: str = HOUR_GRAIN,
) -> str:
    """Builds the request URL with optional query args embedded directly."""
    url = f'{base_url}{path}'
    parts = []
    if from_date:
        parts.append(f'{FROM_DATE}={quote(from_date.isoformat())}')
    if to_date:
        parts.append(f'{TO_DATE}={quote(to_date.isoformat())}')
    if granularity != HOUR_GRAIN:
        parts.append(f'{GRANULARITY}={quote(granularity)}')
    if parts:
        url = f'{url}?{"&".join(parts)}'
    return url


def _get_json(
        client: StatsApiClient,
        url: str,
        tolerate: tuple[HTTPStatus, ...],
) -> Any | None:
    """
    Returns the parsed response body, or None when the status is one of `tolerate`.
    Single door for both endpoints so their error policy is visible at each call site.
    """
    try:
        return client.get(url)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in tolerate:
            return None
        raise


def _follow_pages(
        client: StatsApiClient,
        path: str,
        from_date: datetime | None,
        to_date: datetime | None,
        granularity: str,
        model_class: type,
        tolerate: tuple[HTTPStatus, ...],
) -> Generator:
    """
    Yields parsed model instances following `next_from_date` cursor until None.
    Stops silently if a response status is one of `tolerate`.
    """
    while True:
        url = _build_url(client.base_url, path, from_date, to_date, granularity)
        raw = _get_json(client, url, tolerate)
        if raw is None:
            return
        page = PagedResponse[model_class].model_validate(raw)
        yield from page.items
        if page.next_from_date is None:
            break
        from_date = page.next_from_date
