"""
FastAPI dependency for stats endpoints: accepts X-API-Key header or monitoring JWT fallback.
"""
import secrets
from contextlib import suppress

from fastapi import Header
from fastapi import HTTPException
from fastapi import status

from ecodev_core.app_stats.constants import INVALID_KEY_MSG
from ecodev_core.app_stats.constants import INVALID_MONITORING
from ecodev_core.app_stats.constants import MISSING_AUTH_MSG
from ecodev_core.authentication import get_current_user
from ecodev_core.authentication import MONITORING
from ecodev_core.logger import logger_get
from ecodev_core.settings import SETTINGS

log = logger_get(__name__)

_DEPRECATION_WARNED = False


def _configured_api_key() -> str | None:
    """
    Returns the configured API key, or None if the stats_api section is absent.
    Tolerates configs that predate this feature without raising AttributeError.
    """
    with suppress(AttributeError):
        return getattr(SETTINGS.stats_api, 'api_key', None)
    return None


def _mask_secret(value: str | None) -> str:
    """
    Returns last-4 masked representation: ****abcd, or '<none>' when empty.
    """
    if not value:
        return '<none>'
    return f'****{value[-4:]}' if len(value) > 4 else '****'


async def api_key_or_monitoring(
        x_api_key: str | None = Header(default=None, alias='X-API-Key'),
        authorization: str | None = Header(default=None),
) -> None:
    """
    Dual-path auth for stats endpoints.

    Primary path: `X-API-Key` header compared with `SETTINGS.stats_api.api_key`.
    Fallback: monitoring JWT in `Authorization: Bearer` (deprecated, one-release grace period).

    When `stats_api` config section is absent, the key path is unavailable and only the
    JWT fallback is accepted, so upgrading ecodev_core never breaks existing deployments.
    """
    global _DEPRECATION_WARNED

    configured_key = _configured_api_key()

    if x_api_key is not None:
        if configured_key and secrets.compare_digest(x_api_key, configured_key):
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_KEY_MSG)

    token = _extract_bearer(authorization)
    if token:
        user = get_current_user(token)
        if user and user.user == MONITORING:
            if not _DEPRECATION_WARNED:
                _DEPRECATION_WARNED = True
            return
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=INVALID_MONITORING)
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=MISSING_AUTH_MSG)


def _extract_bearer(authorization: str | None) -> str | None:
    """
    Returns the raw token string from an `Authorization: Bearer <token>` header, or None.
    """
    if authorization and authorization.lower().startswith('bearer '):
        return authorization[7:]
    return None
