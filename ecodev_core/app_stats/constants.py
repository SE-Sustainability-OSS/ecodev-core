"""
Shared constants for the app_stats producer and consumer modules.
"""

TIMEOUT = 30

ACTIVITIES_PATH = '/stats/activities'
PROJECTS_PATH = '/stats/projects'

ACTIVITIES_TAG = 'App Stats'

DEFAULT_PAGE_SIZE = 500

MISSING_AUTH_MSG = 'Provide X-API-Key header'
INVALID_KEY_MSG = 'Invalid API key'

FROM_DATE = 'from_date'
TO_DATE = 'to_date'
GRANULARITY = 'granularity'
GROUP_BY_METHOD = 'group_by_method'
GROUP_BY_APPLICATION = 'group_by_application'
HOUR_GRAIN = 'hour'
MONTH_GRAIN = 'month'
API_KEY_HEADER = 'X-API-Key'
ACCEPT_HEADER = 'Accept'
JSON_MIME = 'application/json'
