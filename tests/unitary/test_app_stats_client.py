"""
Unit tests for StatsApiClient, _build_url, _get_json, _follow_pages.
All HTTP calls are patched so no real network is needed.
"""
import json
from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock
from unittest.mock import patch

import requests
from pydantic import ValidationError

from ecodev_core.app_stats.constants import ACTIVITIES_PATH
from ecodev_core.app_stats.constants import API_KEY_HEADER
from ecodev_core.app_stats.constants import HOUR_GRAIN
from ecodev_core.app_stats.constants import MONTH_GRAIN
from ecodev_core.app_stats.constants import PROJECTS_PATH
from ecodev_core.app_stats.consumer.client import StatsApiClient
from ecodev_core.app_stats.consumer.client import _build_url
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse
from ecodev_core.app_stats.contract import ProjectExport

BASE = 'http://app:80'
KEY = 'secret-key'


def _make_client() -> StatsApiClient:
    return StatsApiClient(base_url=BASE, api_key=KEY)


def _activity_payload(items: list[dict], next_from_date: str | None = None) -> str:
    return json.dumps({'items': items, 'next_from_date': next_from_date})


def _mock_response(body: str, status: int = 200) -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status
    resp.text = body
    resp.json.return_value = json.loads(body)
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(response=resp)
    else:
        resp.raise_for_status.return_value = None
    return resp


SAMPLE_ACTIVITY = {
    'application': 'cf_tool',
    'period_start': '2026-01-15T08:00:00',
    'granularity': HOUR_GRAIN,
    'method': 'compute_pcf',
    'activity_count': 3,
    'unique_users': 2,
}

SAMPLE_PROJECT = {
    'project_id': 'proj-001',
    'name': 'Carbon Audit',
    'creator': 'alice',
    'created_at': '2026-01-10T00:00:00',
    'project_type': 'pcf_only',
}


class BuildUrlTest(TestCase):
    """
    Tests for _build_url URL construction.
    """

    def test_bare_path(self):
        """
        No optional args means only base + path, no query string.
        """
        url = _build_url(BASE, ACTIVITIES_PATH)
        self.assertEqual(url, f'{BASE}{ACTIVITIES_PATH}')

    def test_from_date_encoded(self):
        """
        from_date must be percent-encoded in the query string.
        """
        dt = datetime(2026, 1, 15, 8, 0, 0)
        url = _build_url(BASE, ACTIVITIES_PATH, from_date=dt)
        self.assertIn('from_date=2026-01-15T08', url)

    def test_to_date_encoded(self):
        """
        to_date must be percent-encoded in the query string.
        """
        dt = datetime(2026, 2, 1, 0, 0, 0)
        url = _build_url(BASE, ACTIVITIES_PATH, to_date=dt)
        self.assertIn('to_date=2026-02-01T00', url)

    def test_hour_granularity_omitted(self):
        """
        Default 'hour' granularity should not appear in the query string.
        """
        url = _build_url(BASE, ACTIVITIES_PATH, granularity=HOUR_GRAIN)
        self.assertNotIn('granularity', url)

    def test_month_granularity_included(self):
        """
        Non-default 'month' granularity must appear in the query string.
        """
        url = _build_url(BASE, ACTIVITIES_PATH, granularity=MONTH_GRAIN)
        self.assertIn(f'granularity={MONTH_GRAIN}', url)

    def test_group_by_method_false_emitted(self):
        """
        group_by_method=False must produce group_by_method=false in the URL.
        """
        url = _build_url(BASE, ACTIVITIES_PATH, group_by_method=False)
        self.assertIn('group_by_method=false', url)

    def test_group_by_application_false_emitted(self):
        """
        group_by_application=False must produce group_by_application=false in the URL.
        """
        url = _build_url(BASE, ACTIVITIES_PATH, group_by_application=False)
        self.assertIn('group_by_application=false', url)

    def test_group_by_true_not_emitted(self):
        """
        Default True values should not produce any query parameters.
        """
        url = _build_url(BASE, ACTIVITIES_PATH, group_by_method=True, group_by_application=True)
        self.assertNotIn('group_by', url)


class StatsApiClientValidatorTest(TestCase):
    """
    Tests for StatsApiClient field validators.
    """

    def test_trailing_slash_stripped(self):
        """
        Trailing slash in base_url must be stripped by the validator.
        """
        client = StatsApiClient(base_url='http://app:80/', api_key=KEY)
        self.assertEqual(client.base_url, 'http://app:80')

    def test_non_http_scheme_rejected(self):
        """
        Non-http(s) scheme must raise ValidationError.
        """
        with self.assertRaises(ValidationError):
            StatsApiClient(base_url='ftp://app:80', api_key=KEY)

    def test_empty_api_key_rejected(self):
        """
        Empty api_key must raise ValidationError.
        """
        with self.assertRaises(ValidationError):
            StatsApiClient(base_url=BASE, api_key='')

    def test_frozen_rejects_mutation(self):
        """
        Assigning to a field on a frozen model must raise ValidationError.
        """
        client = _make_client()
        with self.assertRaises(ValidationError):
            client.api_key = 'new-key'


class StatsApiClientHeaderTest(TestCase):
    """
    Tests for the _get_header method.
    """

    def test_header_contains_api_key(self):
        """
        X-API-Key header must equal the configured api_key.
        """
        client = _make_client()
        header = client._get_header()
        self.assertEqual(header[API_KEY_HEADER], KEY)

    def test_header_contains_accept_json(self):
        """
        Accept header must be application/json.
        """
        client = _make_client()
        header = client._get_header()
        self.assertEqual(header['Accept'], 'application/json')

    def test_header_has_exactly_two_keys(self):
        """
        Header must contain exactly two keys: X-API-Key and Accept.
        """
        client = _make_client()
        self.assertEqual(len(client._get_header()), 2)


class FetchActivitiesTest(TestCase):
    """
    Tests for StatsApiClient.fetch_activities pagination and error policy.
    """

    def _page(self, items: list[dict], next_from_date: str | None) -> MagicMock:
        """
        Builds a mock 200 response wrapping a paged activity payload.
        """
        return _mock_response(_activity_payload(items, next_from_date))

    @patch('requests.get')
    def test_single_page_yields_all_rows(self, mock_get):
        """
        A single-page response must yield all its items as ActivityExport instances.
        """
        mock_get.return_value = self._page([SAMPLE_ACTIVITY], next_from_date=None)
        client = _make_client()
        rows = list(client.fetch_activities())
        self.assertEqual(len(rows), 1)
        self.assertIsInstance(rows[0], ActivityExport)
        self.assertEqual(rows[0].method, 'compute_pcf')

    @patch('requests.get')
    def test_two_pages_cursor_forwarded(self, mock_get):
        """
        next_from_date from page 1 must appear as from_date in the page 2 URL.
        """
        page1 = self._page([SAMPLE_ACTIVITY], next_from_date='2026-01-15T09:00:00')
        page2 = self._page([{**SAMPLE_ACTIVITY, 'period_start': '2026-01-15T09:00:00'}],
                           next_from_date=None)
        mock_get.side_effect = [page1, page2]

        client = _make_client()
        rows = list(client.fetch_activities())
        self.assertEqual(len(rows), 2)
        second_url = mock_get.call_args_list[1][1]['url']
        self.assertIn('from_date=2026-01-15T09', second_url)

    @patch('requests.get')
    def test_raises_on_404(self, mock_get):
        """
        /stats/activities is always registered; 404 means the producer is unreachable
        and must not be swallowed.
        """
        mock_get.return_value = _mock_response('{"detail":"not found"}', status=404)
        client = _make_client()
        with self.assertRaises(requests.HTTPError):
            list(client.fetch_activities())

    @patch('requests.get')
    def test_raises_on_500(self, mock_get):
        """
        Server errors must propagate — a dead producer must never look like no activity.
        """
        mock_get.return_value = _mock_response('{"detail":"server error"}', status=500)
        client = _make_client()
        with self.assertRaises(requests.HTTPError):
            list(client.fetch_activities())

    @patch('requests.get')
    def test_month_granularity_in_url(self, mock_get):
        """
        fetch_activities(granularity=MONTH_GRAIN) must include granularity=month in the URL.
        """
        mock_get.return_value = self._page([], next_from_date=None)
        client = _make_client()
        list(client.fetch_activities(granularity=MONTH_GRAIN))
        url = mock_get.call_args[1]['url']
        self.assertIn(f'granularity={MONTH_GRAIN}', url)

    @patch('requests.get')
    def test_group_by_false_in_url(self, mock_get):
        """
        Both group_by flags set to False must appear as false in the URL.
        """
        mock_get.return_value = self._page([], next_from_date=None)
        client = _make_client()
        list(client.fetch_activities(group_by_method=False, group_by_application=False))
        url = mock_get.call_args[1]['url']
        self.assertIn('group_by_method=false', url)
        self.assertIn('group_by_application=false', url)


class FetchProjectsTest(TestCase):
    """
    Tests for StatsApiClient.fetch_projects None-on-404 and normal response.
    """

    @patch('requests.get')
    def test_returns_none_on_404(self, mock_get):
        """
        /stats/projects is optional; 404 means the producer does not expose it.
        None is distinct from [] so callers can leave stored rows untouched.
        """
        mock_get.return_value = _mock_response('{"detail":"not found"}', status=404)
        client = _make_client()
        result = client.fetch_projects()
        self.assertIsNone(result)

    @patch('requests.get')
    def test_returns_list_on_200(self, mock_get):
        """
        A 200 response must return a parsed list of ProjectExport instances.
        """
        payload = json.dumps([SAMPLE_PROJECT])
        mock_get.return_value = _mock_response(payload)
        client = _make_client()
        result = client.fetch_projects()
        self.assertIsNotNone(result)
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], ProjectExport)
        self.assertEqual(result[0].project_id, 'proj-001')

    @patch('requests.get')
    def test_empty_list_not_none(self, mock_get):
        """
        An empty list on 200 is a valid response and must not be treated as None.
        """
        mock_get.return_value = _mock_response('[]')
        client = _make_client()
        result = client.fetch_projects()
        self.assertEqual(result, [])

    @patch('requests.get')
    def test_raises_on_500(self, mock_get):
        """
        Server errors must propagate so the caller knows the producer is unhealthy.
        """
        mock_get.return_value = _mock_response('{"detail":"error"}', status=500)
        client = _make_client()
        with self.assertRaises(requests.HTTPError):
            client.fetch_projects()

    @patch('requests.get')
    def test_url_targets_projects_path(self, mock_get):
        """
        The request URL must contain PROJECTS_PATH.
        """
        mock_get.return_value = _mock_response('[]')
        client = _make_client()
        client.fetch_projects()
        url = mock_get.call_args[1]['url']
        self.assertIn(PROJECTS_PATH, url)
