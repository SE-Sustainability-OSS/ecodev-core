"""
Module testing the UTC datetime helpers and their use in the app_stats pipeline.

Why these helpers exist: sqlmodel>=0.0.45 and psycopg3 map `datetime` columns to
timezone-aware timestamps. Naive datetimes (e.g. `datetime.utcnow()`, or values read
back from a naive column) are no longer interchangeable with aware ones: comparing them
raises `TypeError` and psycopg3 may bind them with a different timezone interpretation.
Every datetime stored or exported must therefore be explicitly UTC-aware.
"""
from datetime import datetime
from datetime import timedelta
from datetime import timezone
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock

from ecodev_core import ActivityExport
from ecodev_core import ProjectExport
from ecodev_core.app_stats.activity_export import _to_export
from ecodev_core.app_stats.consumer.ingest import upsert_remote_activities
from ecodev_core.app_stats.consumer.ingest import upsert_remote_projects
from ecodev_core.date_utils import as_utc
from ecodev_core.date_utils import utc_now

NAIVE = datetime(2026, 1, 15, 8, 0)
PLUS_TWO = timezone(timedelta(hours=2))


class DateUtilsTest(TestCase):
    """
    Class testing `utc_now` and `as_utc`
    """

    def test_utc_now_is_aware_utc(self):
        """
        `utc_now` must be tz-aware, otherwise sqlmodel's datetime columns reject/misread it.
        """
        now = utc_now()
        self.assertIsNotNone(now.tzinfo)
        self.assertEqual(now.utcoffset(), timedelta(0))

    def test_utc_now_comparable_with_aware(self):
        """
        Aware values can be compared; a naive `datetime.utcnow()` would raise TypeError.
        """
        self.assertGreaterEqual(utc_now(), datetime(2026, 1, 1, tzinfo=timezone.utc))
        with self.assertRaises(TypeError):
            _ = utc_now() > NAIVE

    def test_as_utc_none(self):
        """
        Optional columns (e.g. project `modified_at`) stay None.
        """
        self.assertIsNone(as_utc(None))

    def test_as_utc_naive_assumed_utc(self):
        """
        Naive values (read from a naive column) are assumed UTC, not shifted.
        """
        result = as_utc(NAIVE)
        self.assertEqual(result, NAIVE.replace(tzinfo=timezone.utc))
        self.assertEqual(result.utcoffset(), timedelta(0))

    def test_as_utc_converts_other_timezone(self):
        """
        Aware values in another timezone are converted, preserving the instant.
        """
        local = datetime(2026, 1, 15, 10, 0, tzinfo=PLUS_TWO)
        result = as_utc(local)
        self.assertEqual(result, local)
        self.assertEqual(result.hour, 8)
        self.assertEqual(result.utcoffset(), timedelta(0))

    def test_as_utc_idempotent(self):
        """
        Applying `as_utc` twice changes nothing.
        """
        once = as_utc(NAIVE)
        self.assertEqual(as_utc(once), once)


class AppStatsUtcTest(TestCase):
    """
    Class testing that app_stats ingest/export normalise datetimes to aware UTC
    """

    def test_export_period_start_is_aware(self):
        """
        Rows read back from the DB may be naive; the export contract must be UTC-aware so
        consumers on psycopg3 compare/store them consistently.
        """
        row = SimpleNamespace(application='app', period_start=NAIVE, method='m',
                              activity_count=2, unique_users=1)
        export = _to_export(row, 'hour')
        self.assertEqual(export.period_start, NAIVE.replace(tzinfo=timezone.utc))
        self.assertEqual(export.period_start.utcoffset(), timedelta(13))

    def test_upsert_remote_activities_aware(self):
        """
        Remote activities coming from a producer with naive timestamps are stored as UTC.
        """
        session = MagicMock()
        item = ActivityExport(application='app', period_start=NAIVE, activity_count=2,
                              unique_users=1)
        upsert_remote_activities(session, 'app', [item])
        (rows,), _ = session.add_all.call_args
        self.assertEqual(rows[0].period_start.utcoffset(), timedelta(0))
        self.assertEqual(rows[0].ingested_at.utcoffset(), timedelta(0))
        session.commit.assert_called_once()

    def test_upsert_remote_projects_aware(self):
        """
        Project timestamps are normalised, and missing ones are kept as None.
        """
        session = MagicMock()
        item = ProjectExport(project_id='p1', created_at=NAIVE, modified_at=None)
        upsert_remote_projects(session, 'app', [item])
        (rows,), _ = session.add_all.call_args
        self.assertEqual(rows[0].created_at, NAIVE.replace(tzinfo=timezone.utc))
        self.assertIsNone(rows[0].modified_at)
        session.commit.assert_called_once()
