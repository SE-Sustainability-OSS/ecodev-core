"""
Producer-side exports for the app_stats package.
The consumer submodule is intentionally NOT imported here — import it explicitly:
    from ecodev_core.app_stats.consumer import StatsApiClient, ...
"""
from ecodev_core.app_stats.activity_export import get_activities
from ecodev_core.app_stats.api_key import api_key_auth
from ecodev_core.app_stats.constants import ACTIVITIES_PATH
from ecodev_core.app_stats.constants import ACTIVITIES_TAG
from ecodev_core.app_stats.constants import DEFAULT_PAGE_SIZE
from ecodev_core.app_stats.constants import INVALID_KEY_MSG
from ecodev_core.app_stats.constants import MISSING_AUTH_MSG
from ecodev_core.app_stats.constants import PROJECTS_PATH
from ecodev_core.app_stats.constants import TIMEOUT
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
    'api_key_auth',
    'get_stats_router',
    'ACTIVITIES_PATH',
    'ACTIVITIES_TAG',
    'DEFAULT_PAGE_SIZE',
    'INVALID_KEY_MSG',
    'MISSING_AUTH_MSG',
    'PROJECTS_PATH',
    'TIMEOUT',
]
