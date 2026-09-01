"""
HTTP client for polling a remote app's /stats endpoints.
Follows `next_from_date` cursors until the page is exhausted.
"""
import time
from datetime import datetime
from typing import Generator

import requests

from ecodev_core.app_stats.constants import ACTIVITIES_PATH
from ecodev_core.app_stats.constants import PROJECTS_PATH
from ecodev_core.app_stats.constants import TIMEOUT
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse
from ecodev_core.app_stats.contract import ProjectExport
from ecodev_core.logger import logger_get

log = logger_get(__name__)


class StatsApiClient:
    """
    Thin client for pulling activity and project stats from a remote producer app.

    Attributes:
        base_url: Root URL of the producer app (e.g. http://carbon_footprint_backend:80).
        api_key: Value sent as `X-API-Key` header.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key

    def _headers(self) -> dict:
        return {'X-API-Key': self.api_key, 'Accept': 'application/json'}

    def get(self, path: str, params: dict | None = None) -> dict:
        """
        Performs a GET request and returns the parsed JSON body.
        Raises requests.HTTPError on non-2xx responses.
        """
        url = f'{self.base_url}{path}'
        t0 = time.perf_counter()
        log.debug('stats-api GET %s params=%s', url, params)
        response = requests.get(url, headers=self._headers(), params=params, timeout=TIMEOUT)
        log.info('stats-api GET %s → HTTP %d (%.0f ms)',
                 url, response.status_code, (time.perf_counter() - t0) * 1000)
        response.raise_for_status()
        return response.json()

    def fetch_activities(
            self,
            from_date: datetime | None = None,
            to_date: datetime | None = None,
    ) -> Generator[ActivityExport, None, None]:
        """
        Yields all ActivityExport rows, following pagination until exhausted.
        """
        yield from _follow_pages(
            self, ACTIVITIES_PATH, _date_params(from_date, to_date), ActivityExport)

    def fetch_projects(
            self,
            from_date: datetime | None = None,
            to_date: datetime | None = None,
    ) -> Generator[ProjectExport, None, None]:
        """
        Yields all ProjectExport rows, following pagination until exhausted.
        Returns an empty generator if the remote app has no /stats/projects route (404).
        """
        try:
            yield from _follow_pages(
                self, PROJECTS_PATH, _date_params(from_date, to_date), ProjectExport)
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                log.info('%s has no /stats/projects endpoint — skipping', self.base_url)
                return
            raise


def _date_params(
        from_date: datetime | None,
        to_date: datetime | None,
) -> dict:
    """
    Builds the query-param dict for date-range filtering.
    """
    params: dict = {}
    if from_date:
        params['from_date'] = from_date.isoformat()
    if to_date:
        params['to_date'] = to_date.isoformat()
    return params


def _follow_pages(
        client: StatsApiClient,
        path: str,
        params: dict,
        model_class: type,
) -> Generator:
    """
    Yields parsed model instances following `next_from_date` cursor until None.
    Logs each page fetched with running total and cursor position.
    """
    page_num = 0
    total_yielded = 0
    t0 = time.perf_counter()
    while True:
        page_num += 1
        raw = client.get(path, params)
        page = PagedResponse[model_class].model_validate(raw)
        total_yielded += len(page.items)
        log.info('stats-api page %d — %d items (total so far: %d)', page_num, len(page.items),
                 total_yielded)
        for item in page.items:
            yield model_class.model_validate(item.model_dump())
        if page.next_from_date is None:
            log.info('stats-api pagination done — %d items in %d page(s) (%.1fs)',
                     total_yielded, page_num, time.perf_counter() - t0)
            break
        params = {**params, 'from_date': page.next_from_date.isoformat()}
