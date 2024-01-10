"""
Module implementing authentication configuration.
"""
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict


class AuthenticationConfiguration(BaseSettings):
    """
    Simple authentication configuration class
    """
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int
    model_config = SettingsConfigDict(env_file='.env')


AUTH = AuthenticationConfiguration()
