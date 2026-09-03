"""
Opt-in consumer submodule. Not imported by ecodev_core.app_stats or ecodev_core.__init__,
so these tables are never created in producer-only databases.

Import explicitly in consumer apps:
    from ecodev_core.app_stats.consumer import StatsApiClient, RemoteHourlyActivity, ...
"""
from ecodev_core.app_stats.consumer.client import StatsApiClient
from ecodev_core.app_stats.consumer.ingest import delete_lookback_activities
from ecodev_core.app_stats.consumer.ingest import delete_lookback_projects
from ecodev_core.app_stats.consumer.ingest import upsert_remote_activities
from ecodev_core.app_stats.consumer.ingest import upsert_remote_projects
from ecodev_core.app_stats.consumer.processing import get_remote_activities
from ecodev_core.app_stats.consumer.processing import get_remote_projects
from ecodev_core.app_stats.consumer.tables import RemoteAppProject
from ecodev_core.app_stats.consumer.tables import RemoteHourlyActivity

__all__ = [
    'StatsApiClient',
    'RemoteHourlyActivity',
    'RemoteAppProject',
    'delete_lookback_activities',
    'delete_lookback_projects',
    'upsert_remote_activities',
    'upsert_remote_projects',
    'get_remote_activities',
    'get_remote_projects',
]
