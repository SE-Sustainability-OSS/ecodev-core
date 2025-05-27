"""
Module implementing authentication configuration.
"""
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from ecodev_core.settings import SETTINGS


class AuthenticationConfiguration(BaseSettings):
    """
    Simple authentication configuration class
    """
    secret_key: str = ''
    algorithm: str = ''
    access_token_expire_minutes: int = 0
    model_config = SettingsConfigDict(env_file='.env')


AUTH = AuthenticationConfiguration()
SETTINGS_AUTH = SETTINGS.authentication  # type: ignore[attr-defined]
SECRET_KEY = SETTINGS_AUTH.secret_key or AUTH.secret_key
ALGO = SETTINGS_AUTH.algorithm or AUTH.algorithm
EXPIRATION_LENGTH = SETTINGS_AUTH.access_token_expire_minutes or AUTH.access_token_expire_minutes
