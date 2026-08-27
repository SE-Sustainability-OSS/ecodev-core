"""
Producer-side exports for the app_stats package.
The consumer submodule is intentionally NOT imported here — import it explicitly:
    from ecodev_core.app_stats.consumer import StatsApiClient, ...
"""
from ecodev_core.app_stats.activity_export import get_activities
from ecodev_core.app_stats.api_key import api_key_or_monitoring
from ecodev_core.app_stats.contract import ActivityExport
from ecodev_core.app_stats.contract import PagedResponse
from ecodev_core.app_stats.contract import ProjectExport
from ecodev_core.app_stats.contract import ProjectStatsAdapter
from ecodev_core.app_stats.router import get_stats_router

__all__ = [
    'ActivityExport',
    'ProjectExport',
    'PagedResponse',
    'ProjectStatsAdapter',
    'get_activities',
    'api_key_or_monitoring',
    'get_stats_router',
]
