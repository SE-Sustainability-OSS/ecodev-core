"""
Module implementing authentication configuration.
"""
from ecodev_core.settings import SETTINGS


AUTH = SETTINGS.authentication  # type: ignore[attr-defined]
SECRET_KEY = AUTH.secret_key
ALGO = AUTH.algorithm
EXPIRATION_LENGTH = AUTH.access_token_expire_minutes
