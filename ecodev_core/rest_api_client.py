"""
Module implementing a high level Client for calling REST API endpoints
"""
from datetime import datetime
from datetime import timezone
from typing import Any, Optional

import requests
from jose import jwt
from pydantic import BaseModel

from ecodev_core import logger_get
from ecodev_core.authentication import ALGO
from ecodev_core.authentication import SECRET_KEY
from ecodev_core.rest_api_configuration import API_PASSWORD
from ecodev_core.rest_api_configuration import API_USER
from ecodev_core.rest_api_configuration import LOGIN_URL

log = logger_get(__name__)

TIMEOUT = 30
"""
Default request timeout in seconds
"""

class RestApiClient(BaseModel):
    """
    Client for making calls to internal REST API endpoints.

    Attributes:
        _token (dict): Last fetched authentication token.

    NB:
        - When using this class, tokens should be accessed using the property `token` and \
            not `_token` to enforce token auto-refresh and avoid using expired auth. tokens.
    """
    _token: dict = {}

    def _get_new_token(self) -> dict:
        """
        Fetches the authentication token from login API.

        Raises:
            ConnectionRefusedError: If the request returned None

        Returns:
            dict: The authentication token response from login API.
        """
        if (data := handle_response(requests.post(f'{LOGIN_URL}',
                                                  data={'username': API_USER,
                                                        'password': API_PASSWORD}))) is None:
            raise ConnectionRefusedError('Failed to login')
        return data

    @property
    def token(self) -> dict:
        """
        Returns the authentication token with auto-refresh logic if the
        token is expired or within 1 minute to expiration.

        Returns:
            token (dict): Dictionary containing Authentication token
        """
        if self.get_exp() < datetime.now(timezone.utc).timestamp() + 60:
            self._token = self._get_new_token()
        return self._token

    def get_exp(self) -> float:
        """
        Fetch expiration time from existing token `_token`. Defaults to current time.

        Returns:
            float: Token expiration time.
        """
        try:
            payload = jwt.decode(self._token.get('access_token'), SECRET_KEY, algorithms=[ALGO])
            return payload.get('exp', datetime.now(timezone.utc).timestamp())
        except Exception:
            log.warning('Failed to decode token, exp set to current timestamp')
            return datetime.now(timezone.utc).timestamp()

    def _get_header(self) -> dict:
        """
        Returns the headers with authorization information for
        HTTP requests to internal REST APIs.

        Returns:
            dict: HTTP request headers internal REST APIs.
        """
        return {'accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.token.get("access_token")}'}

    def get(self,
            url: str,
            params: Optional[dict] = None,
            timeout: Optional[int] = 30):
        """
        Attributes:
            url (str): Url of the HTTP request
            params (Optional[dict] = None): Query parameters to add to the url. \
                Defaults to None.
            timeout (Optional[int]): HTTP connection timeout. Defaults to 30 (sec).

        Returns:
            response_data (Any): Response body
        """
        return handle_response(requests.get(url=url, headers=self._get_header(),
                                            timeout=timeout, params=params))

    def post(self,
             url: str,
             data: Optional[Any] = None,
             params: Optional[dict] = None,
             timeout: Optional[int] = 30):
        """
        Attributes:
            url (str): Url of the HTTP request
            data (Optional[Any] = None): The body/payload of the request. Defaults to None.
            params (Optional[dict] = None): Query parameters to add to the url. \
                Defaults to None.
            timeout (Optional[int]): HTTP connection timeout. Defaults to 30 (sec).

        Returns:
            response_data (Any): Response body
        """
        return handle_response(requests.post(url=url, json=data, headers=self._get_header(),
                                             timeout=timeout, params=params))

    def put(self,
            url: str,
            data: Any,
            params: Optional[dict] = None,
            timeout: Optional[int] = 30):
        """
        Attributes:
            url (str): Url of the HTTP request
            data (Any): The body/payload of the request.
            params (Optional[dict]): Requests parameters to add to the url. \
                Defaults to None.
            timeout (Optional[int]): HTTP connection timeout. Defaults to 30 (sec).

        Returns:
            response_data (Any): Response body
        """
        return handle_response(requests.put(url=url, json=data, headers=self._get_header(),
                                            timeout=timeout, params=params))

    def patch(self,
              url: str,
              data: Any,
              params: Optional[dict] = None,
              timeout: Optional[int] = 30):
        """
        Attributes:
            url (str): Url of the HTTP request
            data (Optional[Any] = None): The body/payload of the request. Defaults to None.
            params (Optional[dict]): Query parameters to add to the url. \
                Defaults to None.
            timeout (Optional[int]): HTTP connection timeout. Defaults to 30 (sec).

        Returns:
            response_data (Any): Response body
        """
        return handle_response(requests.patch(url=url, json=data, headers=self._get_header(),
                                              timeout=timeout, params=params))

    def delete(self,
               url: str,
               params: Optional[dict] = None,
               timeout: Optional[int] = 30):
        """
        Attributes:
            url (str): Url of the HTTP request
            params (Optional[dict]): Query parameters to add to the url. \
                Defaults to None.
            timeout (Optional[int]): HTTP connection timeout. Defaults to 30 (sec).

        Returns:
            response_data (Any): Response body
        """
        return handle_response(requests.delete(url=url, headers=self._get_header(),
                                               timeout=timeout, params=params))


def handle_response(response: requests.Response):
    """
    Extracts the data from the http response object

    Attributes:
        response (requests.Response): HTTP response object to handle

    Raises:
        HTTPError: If the HTTP request returned an unsuccessful status code.
        Exception: For any other error parsing the response.

    Returns:
        data (Any): Extracted data from HTTP response object
    """
    try:
        response.raise_for_status()
        response_body = response.json()
        return response_body
    except requests.HTTPError as http_exception:
        log.error(f'Error {response.status_code} : {response.text}')
        raise http_exception
    except Exception as e:
        log.error('Failed to parse response body')
        raise e


REST_API_CLIENT: Optional[RestApiClient] = None


def get_rest_api_client() -> RestApiClient:
    """
    Initiate or return existing RestApiClient instance
    """
    global REST_API_CLIENT

    if REST_API_CLIENT is None:
        REST_API_CLIENT = RestApiClient()

    return REST_API_CLIENT
