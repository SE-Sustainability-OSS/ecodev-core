"""
Module implementing restapi authentication configuration.
"""
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from ecodev_core.settings import SETTINGS


class RestApiConfiguration(BaseSettings):
    """
    Simple authentication configuration class
    """
    host: str = ''
    user: str = ''
    password: str = ''
    model_config = SettingsConfigDict(env_file='.env')


API_AUTH = RestApiConfiguration()


LOGIN_URL = f'{(SETTINGS.api.host or API_AUTH.host)}/login'
API_USER = SETTINGS.api.user or API_AUTH.user
API_PASSWORD = SETTINGS.api.password or API_AUTH.password
