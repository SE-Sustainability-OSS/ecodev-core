"""
Module defining a dynamic setting class
"""
from contextlib import suppress
from pathlib import Path

from pydantic.v1.utils import deep_update
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from ecodev_core.deployment import Deployment
from ecodev_core.list_utils import dict_to_class
from ecodev_core.read_write import load_yaml_file


class DeploymentSetting(BaseSettings):
    """
    Settings class used to load the deployment type from environment variables.
    """
    environment: str = 'local'
    base_path: str = '/app'
    model_config = SettingsConfigDict(env_file='.env')


DEPLOYMENT_SETTINGS = DeploymentSetting()
DEPLOYMENT = Deployment(DEPLOYMENT_SETTINGS.environment.lower())
BASE_PATH = Path(DEPLOYMENT_SETTINGS.base_path)


class Settings:
    """
    Dynami setting class, loading yaml configuration from config file, possibly overwriting some of
    this configuration with additional information coming from a secret file.
    """

    def __init__(self, base_path: Path = BASE_PATH, deployment: Deployment = DEPLOYMENT):
        """
        Dynamically setting Settings attributes, doing so recursively. Attributes are loaded
         from config file, possibly overwriting some of this configuration with additional
         information coming from a secret file.
        """
        self.deployment = deployment
        with suppress(FileNotFoundError):
            data = load_yaml_file(base_path / 'config' / f'{deployment.value}.yaml')
            if (secrets_file := base_path / 'secrets' / f'{deployment.value}.yaml').exists():
                data = deep_update(data, load_yaml_file(secrets_file))
            for k, v in dict_to_class(data).items():
                setattr(self, k, v)


SETTINGS = Settings()
