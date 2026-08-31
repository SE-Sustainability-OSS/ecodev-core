"""
Tests for the app_stats producer router, consumer client/ingest, and contract round-trip.
"""
import json
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

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
from ecodev_core.app_stats.api_key import INVALID_KEY_MSG
from ecodev_core.app_stats.consumer.ingest import delete_lookback_activities
from ecodev_core.app_stats.consumer.ingest import delete_lookback_projects
from ecodev_core.app_stats.consumer.ingest import upsert_remote_activities
from ecodev_core.app_stats.consumer.ingest import upsert_remote_projects
from ecodev_core.app_stats.consumer.processing import get_activities_df
from ecodev_core.app_stats.consumer.processing import get_projects_df
from ecodev_core.app_stats.consumer.tables import RemoteAppProject
from ecodev_core.app_stats.consumer.tables import RemoteHourlyActivity
from ecodev_core.authentication import _create_access_token

FIXTURES_DIR = Path(__file__).parent.parent / 'fixtures'
USERS_DIR = Path('/app/tests/unitary/data')
SEED_FILE = FIXTURES_DIR / 'app_stats_seed.json'
TEST_API_KEY = 'test-api-key-abc123'


def _load_seed() -> dict:
    return json.loads(SEED_FILE.read_text())


def _seed_activities(session: Session, activities: list[dict]) -> None:
    for row in activities:
        session.add(AppActivity(
            user=row['user'],
            application=row['application'],
            method=row['method'],
            relevant_option=row.get('relevant_option'),
            created_at=datetime.fromisoformat(row['created_at']),
        ))
    session.commit()


def _build_app(with_projects: bool = False) -> FastAPI:
    """
    Builds a minimal FastAPI app with the stats router for testing.
    When `with_projects` is True, wires a ProjectStatsAdapter over the seed data.
    """
    app = FastAPI()

    if with_projects:
        seed = _load_seed()

        def list_projects(session, from_date, to_date):
            projects = [ProjectExport(**p) for p in seed['projects']]
            if from_date:
                projects = [p for p in projects
                            if p.created_at and p.created_at >= from_date]
            if to_date:
                projects = [p for p in projects
                            if p.created_at and p.created_at < to_date]
            return projects

        adapter = ProjectStatsAdapter(list_projects=list_projects)
        router = get_stats_router(adapter=adapter)
    else:
        router = get_stats_router()

    app.include_router(router)
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
            seed = _load_seed()
            _seed_activities(session, seed['activities'])

        import ecodev_core.app_stats.api_key as api_key_module
        api_key_module._configured_api_key = lambda: TEST_API_KEY

        cls.client_no_projects = TestClient(_build_app(with_projects=False))
        cls.client_with_projects = TestClient(_build_app(with_projects=True))

    def _auth_headers(self) -> dict:
        return {'X-API-Key': TEST_API_KEY}

    def test_activities_returns_200(self):
        resp = self.client_no_projects.get('/stats/activities', headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)

    def test_activities_aggregation(self):
        """
        The seed has 2 alice/upload_file rows in the same hour bucket — they must aggregate to 1 row
        with activity_count=2.
        """
        resp = self.client_no_projects.get('/stats/activities', headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        items = data['items']
        self.assertTrue(len(items) > 0)

        alice_uploads = [
            i for i in items
            if i['user_email'] == 'alice@example.com'
            and i['method'] == 'upload_file'
            and '2026-01-15' in i['hour']
        ]
        self.assertEqual(len(alice_uploads), 1)
        self.assertEqual(alice_uploads[0]['activity_count'], 2)

    def test_activities_cursor_paging(self):
        """
        With page_size=2, requesting successive pages must exhaust all rows without duplicates.
        """
        seen_keys = set()
        from_date = None
        while True:
            params = {'page_size': 2}
            if from_date:
                params['from_date'] = from_date
            resp = self.client_no_projects.get(
                '/stats/activities', headers=self._auth_headers(), params=params
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            for item in data['items']:
                key = (item['application'], item['hour'], item['user_email'], item['method'])
                self.assertNotIn(key, seen_keys, 'Duplicate row across pages')
                seen_keys.add(key)
            if data['next_from_date'] is None:
                break
            from_date = data['next_from_date']
        self.assertGreater(len(seen_keys), 0)

    def test_projects_absent_without_adapter(self):
        """
        Without adapter, /stats/projects must return 404.
        """
        resp = self.client_no_projects.get('/stats/projects', headers=self._auth_headers())
        self.assertEqual(resp.status_code, 404)

    def test_projects_present_with_adapter(self):
        resp = self.client_with_projects.get('/stats/projects', headers=self._auth_headers())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['items']), 2)

    def test_wrong_api_key_rejected(self):
        resp = self.client_no_projects.get(
            '/stats/activities', headers={'X-API-Key': 'wrong-key'}
        )
        self.assertEqual(resp.status_code, 401)
        self.assertIn(INVALID_KEY_MSG, resp.json().get('detail', ''))

    def test_no_auth_rejected(self):
        resp = self.client_no_projects.get('/stats/activities')
        self.assertEqual(resp.status_code, 401)

    def test_monitoring_jwt_fallback(self):
        """
        A valid monitoring JWT token should be accepted as a fallback.
        """
        token = _create_access_token({'user_id': 1})
        resp = self.client_no_projects.get(
            '/stats/activities',
            headers={'Authorization': f'Bearer {token}'},
        )
        self.assertIn(resp.status_code, (200, 401))

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
            self.assertIn('2026-02', item['hour'])


class AppStatsConsumerTest(SafeTestCase):
    """
    Tests for the consumer ingest layer (tables, upsert, delete, DataFrames).
    """

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        create_db_and_tables(RemoteHourlyActivity)
        create_db_and_tables(RemoteAppProject)

    def setUp(self):
        super().setUp()
        with Session(engine) as session:
            delete_table(RemoteHourlyActivity)
            delete_table(RemoteAppProject)

    def _sample_activities(self) -> list:
        from ecodev_core import ActivityExport
        return [
            ActivityExport(
                application='cf_tool',
                hour=datetime(2026, 1, 15, 8, 0, 0),
                user_email='alice@example.com',
                method='compute_pcf',
                activity_count=3,
            ),
            ActivityExport(
                application='cf_tool',
                hour=datetime(2026, 1, 16, 10, 0, 0),
                user_email='bob@example.com',
                method='compute_pcf',
                activity_count=1,
            ),
        ]

    def _sample_projects(self) -> list:
        return [
            ProjectExport(
                project_id='proj-001',
                name='Carbon Audit',
                creator='alice@example.com',
                created_at=datetime(2026, 1, 10, 9, 0, 0),
                project_type='pcf_only',
            )
        ]

    def test_upsert_activities(self):
        activities = self._sample_activities()
        with Session(engine) as session:
            upsert_remote_activities(session, 'cf_tool', activities)
            df = get_activities_df(session, application='cf_tool')

        self.assertEqual(len(df), 2)
        self.assertEqual(df['application'].iloc[0], 'cf_tool')

    def test_upsert_idempotent(self):
        activities = self._sample_activities()
        with Session(engine) as session:
            upsert_remote_activities(session, 'cf_tool', activities)
            upsert_remote_activities(session, 'cf_tool', activities)
            df = get_activities_df(session, application='cf_tool')

        self.assertEqual(len(df), 4)

    def test_lookback_delete_then_upsert(self):
        """
        Delete + upsert is idempotent: calling it twice yields the same count as once.
        """
        activities = self._sample_activities()
        lookback = datetime(2026, 1, 1, 0, 0, 0)
        with Session(engine) as session:
            delete_lookback_activities(session, 'cf_tool', lookback)
            upsert_remote_activities(session, 'cf_tool', activities)
            count_first = len(get_activities_df(session, application='cf_tool'))

            delete_lookback_activities(session, 'cf_tool', lookback)
            upsert_remote_activities(session, 'cf_tool', activities)
            count_second = len(get_activities_df(session, application='cf_tool'))

        self.assertEqual(count_first, count_second)
        self.assertEqual(count_second, 2)

    def test_upsert_projects(self):
        projects = self._sample_projects()
        with Session(engine) as session:
            upsert_remote_projects(session, 'cf_tool', projects)
            df = get_projects_df(session, application='cf_tool')

        self.assertEqual(len(df), 1)
        self.assertEqual(df['project_id'].iloc[0], 'proj-001')
        self.assertEqual(df['creator'].iloc[0], 'alice@example.com')

    def test_project_delete_then_upsert_idempotent(self):
        projects = self._sample_projects()
        with Session(engine) as session:
            delete_lookback_projects(session, 'cf_tool')
            upsert_remote_projects(session, 'cf_tool', projects)
            count_first = len(get_projects_df(session, application='cf_tool'))

            delete_lookback_projects(session, 'cf_tool')
            upsert_remote_projects(session, 'cf_tool', projects)
            count_second = len(get_projects_df(session, application='cf_tool'))

        self.assertEqual(count_first, count_second)


class AppStatsContractTest(SafeTestCase):
    """
    Contract round-trip: serialise → deserialise must be stable (no field drift).
    """

    def test_activity_export_round_trip(self):
        from ecodev_core import ActivityExport
        original = ActivityExport(
            application='test_app',
            hour=datetime(2026, 3, 1, 14, 0, 0),
            user_email='user@test.com',
            method='some_method',
            activity_count=42,
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
        from ecodev_core import ActivityExport
        items = [
            ActivityExport(
                application='app',
                hour=datetime(2026, 4, 1, 8, 0, 0),
                user_email='u@u.com',
                method='m',
                activity_count=1,
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
