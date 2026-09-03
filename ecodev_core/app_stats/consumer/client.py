"""
HTTP client for polling a remote app's /stats endpoints.
Follows `next_from_date` cursors until the page is exhausted.
"""
from datetime import datetime
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


class StatsApiClient(RestApiClient):
    """
    Client pulling activity and project stats from a remote producer app.

    Attributes:
        base_url: Root URL of the producer app (e.g. http://carbon_footprint_backend:80).
        api_key: Value sent as X-API-Key header.
    """
    model_config = ConfigDict(frozen=True)
    api_key: str

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

    def fetch_activities(
            self,
            from_date: datetime | None = None,
            to_date: datetime | None = None,
            granularity: str = HOUR_GRAIN,
    ) -> Generator[ActivityExport, None, None]:
        """
        Yields all ActivityExport rows for the given granularity, following pagination.
        """
        yield from _follow_pages(self, ACTIVITIES_PATH, from_date, to_date,
                                  granularity, ActivityExport, tolerate_missing=False)

    def fetch_projects(
            self,
            from_date: datetime | None = None,
            to_date: datetime | None = None,
    ) -> Generator[ProjectExport, None, None]:
        """
        Yields all ProjectExport rows, following pagination until exhausted.
        Returns an empty generator if the remote app has no /stats/projects route (404).
        """
        yield from _follow_pages(self, PROJECTS_PATH, from_date, to_date,
                                  HOUR_GRAIN, ProjectExport, tolerate_missing=True)


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


def _follow_pages(
        client: StatsApiClient,
        path: str,
        from_date: datetime | None,
        to_date: datetime | None,
        granularity: str,
        model_class: type,
        tolerate_missing: bool,
) -> Generator:
    """
    Yields parsed model instances following `next_from_date` cursor until None.
    When `tolerate_missing` is True, a 404 response silently returns an empty generator.
    """
    while True:
        url = _build_url(client.base_url, path, from_date, to_date, granularity)
        try:
            raw = client.get(url)
        except requests.HTTPError as exc:
            if tolerate_missing and exc.response is not None and exc.response.status_code == 404:
                return
            raise
        page = PagedResponse[model_class].model_validate(raw)
        yield from page.items
        if page.next_from_date is None:
            break
        from_date = page.next_from_date
