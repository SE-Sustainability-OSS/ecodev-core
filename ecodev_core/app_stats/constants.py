"""
Shared constants for the app_stats producer and consumer modules.
"""

TIMEOUT = 30

ACTIVITIES_PATH = '/stats/activities'
PROJECTS_PATH = '/stats/projects'

ACTIVITIES_TAG = 'App Stats'

DEFAULT_PAGE_SIZE = 500

MISSING_AUTH_MSG = 'Provide X-API-Key header or a monitoring bearer token'
INVALID_KEY_MSG = 'Invalid API key'
INVALID_MONITORING = 'Bearer token is not a monitoring user'
