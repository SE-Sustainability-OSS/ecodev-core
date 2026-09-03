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
API_KEY_HEADER = 'X-API-Key'
ACCEPT_HEADER = 'Accept'
JSON_MIME = 'application/json'
