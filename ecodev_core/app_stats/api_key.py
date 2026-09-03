"""
FastAPI dependency for stats endpoints: validates the X-API-Key header.
"""
import secrets
from contextlib import suppress

from fastapi import Header
from fastapi import HTTPException
from fastapi import status

from ecodev_core.app_stats.constants import INVALID_KEY_MSG
from ecodev_core.app_stats.constants import MISSING_AUTH_MSG
from ecodev_core.settings import SETTINGS


async def api_key_auth(
        x_api_key: str | None = Header(default=None, alias='X-API-Key'),
) -> None:
    """
    Validates the X-API-Key header against SETTINGS.stats_api.api_key.
    Raises HTTP 401 when the header is absent or the key does not match.
    """
    if x_api_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=MISSING_AUTH_MSG)
    configured_key = _configured_api_key()
    if configured_key and secrets.compare_digest(x_api_key, configured_key):
        return
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_KEY_MSG)


def _configured_api_key() -> str | None:
    """
    Returns the configured API key, or None if the stats_api section is absent.
    Tolerates configs that predate this feature without raising AttributeError.
    """
    with suppress(AttributeError):
        return getattr(SETTINGS.stats_api, 'api_key', None)
    return None
