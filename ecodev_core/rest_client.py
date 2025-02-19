from datetime import datetime
from functools import partial
from typing import Dict
from typing import Union

import requests
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from ecodev_core import log_critical
from ecodev_core import logger_get
from ecodev_core.authentication import BEARER
from ecodev_core.authentication import EXPIRES_AT
log = logger_get(__name__)


class APIClientConfig(BaseSettings):
    """
    Simple authentication configuration class
    """
    username: str
    password: str
    api_url: str
    auth_route: str
    model_config = SettingsConfigDict(env_file='.env', env_prefix='API_')

    def get_login_info(self):
        return {'username': self.username, 'password': self.password}


class APIClient:
    client_config: APIClientConfig = None
    token: Dict = {}

    def __init__(self, client_config: APIClientConfig):
        self.client_config = client_config
        self.token = self._get_new_token()

    def _get_new_token(self):

        try:
            response = requests.post(f'{self.client_config.auth_route}', json=self.client_config)
            if not response.ok:
                raise ConnectionRefusedError(response.json())
            return response.json()
        except Exception as e:
            log_critical(e, log)

    def _refresh_token(self):
        if not self.token or self.token[EXPIRES_AT] < datetime.now().timestamp() - 60:  # noqa: E501
            log.warning('refreshing token')
            self.token = self._get_new_token()

    def _get_header(self):
        self._refresh_token()
        return {'Authorization': f'{BEARER} {self.token["access_token"]}'}

    def _safe_call(self, route, method):
        try:
            response = method(url=f'{self.client_config.api_url}{route}',
                              headers=self._get_header())
            if not response.ok:
                raise ConnectionRefusedError(response.content)
            return response.json()
        except Exception as e:
            log_critical(f'get {route} failed:\n{e}', log)

    def get(self, route):
        """
        Call a get route with authentication, capturing and logging any errors
        """

        return self._safe_call(route, requests.get, )

    def post(self, route, data):
        """
        Call a post route with authentication, capturing and logging any errors
        """
        return self._safe_call(route, partial(requests.post, json=data))

    def put(self, route, data):
        """
        Call a put route with authentication, capturing and logging any errors
        """
        return self._safe_call(route, partial(requests.put, json=data))


CLIENT: Union[APIClient, None] = None


def get_client(client_config: APIClientConfig = None) -> APIClient:
    """
    Get the factset client
    """
    global CLIENT

    if CLIENT is None:
        CLIENT = APIClient(client_config or APIClientConfig())

    return CLIENT
