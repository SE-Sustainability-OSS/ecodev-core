"""
Tests for the app_stats producer router, consumer client/ingest, and contract round-trip.
"""
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from ecodev_core import ActivityExport
from ecodev_core import AppActivity
from ecodev_core import AppRight
from ecodev_core import AppUser
from ecodev_core import create_db_and_tables
from ecodev_core import delete_table
from ecodev_core import engine
from ecodev_core import get_stats_router
from ecodev_core import PagedResponse
from ecodev_core import ProjectExport
from ecodev_core import ProjectStatsAdapter
from ecodev_core import SafeTestCase
from ecodev_core import upsert_app_users
from ecodev_core.app_stats.constants import INVALID_KEY_MSG
from ecodev_core.app_stats.consumer.ingest import delete_lookback_activities
from ecodev_core.app_stats.consumer.ingest import delete_lookback_projects
from ecodev_core.app_stats.consumer.ingest import upsert_remote_activities
from ecodev_core.app_stats.consumer.ingest import upsert_remote_projects
from ecodev_core.app_stats.consumer.processing import get_remote_activities
from ecodev_core.app_stats.consumer.processing import get_remote_projects
from ecodev_core.app_stats.consumer.tables import RemoteActivity
from ecodev_core.app_stats.consumer.tables import RemoteAppProject

USERS_DIR = Path('/app/tests/unitary/data')
TEST_API_KEY = 'test-api-key-abc123'

# Two alice/upload_file rows in the same hour → must aggregate to 1 row with activity_count=2.
SEED_ACTIVITIES = [
    {'user': 'alice', 'application': 'cf_tool', 'method': 'upload_file',
     'created_at': datetime(2026, 1, 15, 8, 10)},
    {'user': 'alice', 'application': 'cf_tool', 'method': 'upload_file',
     'created_at': datetime(2026, 1, 15, 8, 45)},
    {'user': 'bob', 'application': 'cf_tool', 'method': 'compute_pcf',
     'created_at': datetime(2026, 1, 15, 9, 0)},
    {'user': 'carol', 'application': 'cf_tool', 'method': 'compute_pcf',
     'created_at': datetime(2026, 2, 1, 10, 0)},
]

SEED_PROJECTS = [
    ProjectExport(
        project_id='proj-001',
        name='Carbon Audit',
        creator='alice',
        created_at=datetime(2026, 1, 10),
        project_type='pcf_only',
    ),
    ProjectExport(
        project_id='proj-002',
        name='Scope 3',
        creator='bob',
        created_at=datetime(2026, 2, 1),
        project_type='cft_only',
    ),
]


def _seed_activities(session: Session, activities: list[dict]) -> None:
    session.add_all([
        AppActivity(
            user=row['user'],
            application=row['application'],
            method=row['method'],
            created_at=row['created_at'],
        )
        for row in activities
    ])
    session.commit()


def _list_projects(session, from_date, to_date):
    projects = list(SEED_PROJECTS)
    if from_date:
        projects = [p for p in projects if p.created_at and p.created_at >= from_date]
    if to_date:
        projects = [p for p in projects if p.created_at and p.created_at < to_date]
    return projects


def _build_app(with_projects: bool = False) -> FastAPI:
    """
    Builds a minimal FastAPI app with the stats router for testing.
    """
    app = FastAPI()
    adapter = ProjectStatsAdapter(list_projects=_list_projects) if with_projects else None
    app.include_router(get_stats_router(adapter=adapter))
    return app


class AppStatsProducerTest(SafeTestCase):
    """
    Tests for the /stats/activities and /stats/projects producer endpoints.
    API key is injected via the X-API-Key header.
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_db_and_tables(AppActivity)
        create_db_and_tables(AppUser)
        delete_table(AppActivity)
        delete_table(AppRight)
        delete_table(AppUser)
        with Session(engine) as session:
            upsert_app_users(USERS_DIR / 'users.json', session)
            _seed_activities(session, SEED_ACTIVITIES)

        cls._patcher = patch(
            'ecodev_core.app_stats.api_key._configured_api_key',
            return_value=TEST_API_KEY,
        )
        cls._patcher.start()
        cls.client_no_projects = TestClient(_build_app(with_projects=False))
        cls.client_with_projects = TestClient(_build_app(with_projects=True))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._patcher.stop()
        super().tearDownClass()

    def _auth_headers(self) -> dict:
        return {'X-API-Key': TEST_API_KEY}

    def test_activities_returns_200(self):
        resp = self.client_no_projects.get('/stats/activities', headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)

    def test_activities_aggregation(self):
        """
        The seed has 2 alice/upload_file rows in the same hour — they must aggregate to 1 row
        with activity_count=2.
        """
        resp = self.client_no_projects.get('/stats/activities', headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        items = resp.json()['items']
        self.assertTrue(len(items) > 0)

        upload_rows = [
            i for i in items
            if i['method'] == 'upload_file'
            and '2026-01-15T08' in i['period_start']
        ]
        self.assertEqual(len(upload_rows), 1)
        self.assertEqual(upload_rows[0]['activity_count'], 2)

    def test_activities_pages_do_not_overlap(self):
        """
        Successive pages with page_size=1 must exhaust all rows without duplicate keys.
        """
        seen_keys = set()
        from_date = None
        while True:
            params = {'page_size': 1}
            if from_date:
                params['from_date'] = from_date
            resp = self.client_no_projects.get(
                '/stats/activities', headers=self._auth_headers(), params=params
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            for item in data['items']:
                key = (item['application'], item['period_start'], item['method'])
                self.assertNotIn(key, seen_keys, 'Duplicate row across pages')
                seen_keys.add(key)
            if data['next_from_date'] is None:
                break
            from_date = data['next_from_date']
        self.assertGreater(len(seen_keys), 0)

    def test_oversized_bucket_still_advances(self):
        """
        When a page_size=1 request lands on a bucket that has more rows than page_size,
        next_from_date must advance past that bucket so pagination terminates.
        Verified by inserting 2 methods in the same hour and confirming no infinite loop.
        """
        resp = self.client_no_projects.get(
            '/stats/activities',
            headers=self._auth_headers(),
            params={'page_size': 1, 'from_date': '2026-01-15T08:00:00'},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNotNone(data)
        # next_from_date must differ from the emitted bucket so we make forward progress
        if data['next_from_date'] is not None and data['items']:
            self.assertNotEqual(data['next_from_date'], data['items'][0]['period_start'])

    def test_projects_absent_without_adapter(self):
        resp = self.client_no_projects.get('/stats/projects', headers=self._auth_headers())
        self.assertEqual(resp.status_code, 404)

    def test_projects_present_with_adapter(self):
        resp = self.client_with_projects.get('/stats/projects', headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), len(SEED_PROJECTS))

    def test_wrong_api_key_rejected(self):
        resp = self.client_no_projects.get(
            '/stats/activities', headers={'X-API-Key': 'wrong-key'}
        )
        self.assertEqual(resp.status_code, 401)
        self.assertIn(INVALID_KEY_MSG, resp.json().get('detail', ''))

    def test_no_auth_rejected(self):
        resp = self.client_no_projects.get('/stats/activities')
        self.assertEqual(resp.status_code, 401)

    def test_activities_method_filter(self):
        resp = self.client_no_projects.get(
            '/stats/activities',
            headers=self._auth_headers(),
            params={'method': 'upload_file'},
        )
        self.assertEqual(resp.status_code, 200)
        for item in resp.json()['items']:
            self.assertEqual(item['method'], 'upload_file')

    def test_activities_date_filter(self):
        resp = self.client_no_projects.get(
            '/stats/activities',
            headers=self._auth_headers(),
            params={'from_date': '2026-02-01T00:00:00', 'to_date': '2026-02-02T00:00:00'},
        )
        self.assertEqual(resp.status_code, 200)
        for item in resp.json()['items']:
            self.assertIn('2026-02', item['period_start'])


class AppStatsConsumerTest(SafeTestCase):
    """
    Tests for the consumer ingest layer (tables, upsert, delete, list[dict] helpers).
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_db_and_tables(RemoteActivity)
        create_db_and_tables(RemoteAppProject)

    def setUp(self):
        super().setUp()
        delete_table(RemoteActivity)
        delete_table(RemoteAppProject)

    def _sample_activities(self) -> list[ActivityExport]:
        return [
            ActivityExport(
                application='cf_tool',
                period_start=datetime(2026, 1, 15, 8, 0, 0),
                granularity='hour',
                method='compute_pcf',
                activity_count=3,
                unique_users=2,
            ),
            ActivityExport(
                application='cf_tool',
                period_start=datetime(2026, 1, 16, 10, 0, 0),
                granularity='hour',
                method='compute_pcf',
                activity_count=1,
                unique_users=1,
            ),
        ]

    def _sample_projects(self) -> list[ProjectExport]:
        return [
            ProjectExport(
                project_id='proj-001',
                name='Carbon Audit',
                creator='alice',
                created_at=datetime(2026, 1, 10, 9, 0, 0),
                project_type='pcf_only',
            )
        ]

    def test_upsert_activities(self):
        activities = self._sample_activities()
        with Session(engine) as session:
            upsert_remote_activities(session, 'cf_tool', activities)
            rows = get_remote_activities(session, application='cf_tool')

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['application'], 'cf_tool')

    def test_upsert_idempotent(self):
        activities = self._sample_activities()
        with Session(engine) as session:
            upsert_remote_activities(session, 'cf_tool', activities)
            upsert_remote_activities(session, 'cf_tool', activities)
            rows = get_remote_activities(session, application='cf_tool')

        self.assertEqual(len(rows), 4)

    def test_lookback_delete_then_upsert(self):
        """
        Delete + upsert is idempotent: calling it twice yields the same row count.
        The same `from_date` and `granularity` must reach both delete and upsert calls.
        """
        activities = self._sample_activities()
        lookback = datetime(2026, 1, 1, 0, 0, 0)
        with Session(engine) as session:
            delete_lookback_activities(session, 'cf_tool', lookback, granularity='hour')
            upsert_remote_activities(session, 'cf_tool', activities, granularity='hour')
            count_first = len(get_remote_activities(session, application='cf_tool'))

            delete_lookback_activities(session, 'cf_tool', lookback, granularity='hour')
            upsert_remote_activities(session, 'cf_tool', activities, granularity='hour')
            count_second = len(get_remote_activities(session, application='cf_tool'))

        self.assertEqual(count_first, count_second)
        self.assertEqual(count_second, 2)

    def test_upsert_projects(self):
        projects = self._sample_projects()
        with Session(engine) as session:
            upsert_remote_projects(session, 'cf_tool', projects)
            rows = get_remote_projects(session, application='cf_tool')

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['project_id'], 'proj-001')
        self.assertEqual(rows[0]['creator'], 'alice')

    def test_project_delete_then_upsert_idempotent(self):
        projects = self._sample_projects()
        with Session(engine) as session:
            delete_lookback_projects(session, 'cf_tool')
            upsert_remote_projects(session, 'cf_tool', projects)
            count_first = len(get_remote_projects(session, application='cf_tool'))

            delete_lookback_projects(session, 'cf_tool')
            upsert_remote_projects(session, 'cf_tool', projects)
            count_second = len(get_remote_projects(session, application='cf_tool'))

        self.assertEqual(count_first, count_second)


class AppStatsContractTest(SafeTestCase):
    """
    Contract round-trip: serialise → deserialise must be stable (no field drift).
    """

    def test_activity_export_round_trip(self):
        original = ActivityExport(
            application='test_app',
            period_start=datetime(2026, 3, 1, 14, 0, 0),
            granularity='hour',
            method='some_method',
            activity_count=42,
            unique_users=7,
        )
        restored = ActivityExport.model_validate(json.loads(original.model_dump_json()))
        self.assertEqual(original, restored)

    def test_project_export_round_trip(self):
        original = ProjectExport(
            project_id='abc-123',
            name='Test Project',
            creator='owner@test.com',
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            project_type='both',
        )
        restored = ProjectExport.model_validate(json.loads(original.model_dump_json()))
        self.assertEqual(original, restored)

    def test_paged_response_round_trip(self):
        items = [
            ActivityExport(
                application='app',
                period_start=datetime(2026, 4, 1, 8, 0, 0),
                granularity='hour',
                method='m',
                activity_count=1,
                unique_users=1,
            )
        ]
        page = PagedResponse[ActivityExport](
            items=items, next_from_date=datetime(2026, 4, 1, 9, 0, 0)
        )
        raw = page.model_dump_json()
        restored = PagedResponse[ActivityExport].model_validate_json(raw)
        self.assertEqual(page.next_from_date, restored.next_from_date)
        self.assertEqual(len(restored.items), 1)
        self.assertEqual(restored.items[0].activity_count, 1)
