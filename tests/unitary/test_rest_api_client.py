"""
Module testing the package's rest api client
"""
from datetime import datetime
from datetime import timezone
from unittest.mock import MagicMock
from unittest.mock import PropertyMock
from unittest.mock import patch

import requests

from ecodev_core import RestApiClient, SafeTestCase
from ecodev_core import get_rest_api_client
from ecodev_core import handle_response
from ecodev_core.auth_configuration import ALGO
from ecodev_core.auth_configuration import SECRET_KEY
import ecodev_core.rest_api_client as rac


class RestApiClientFactoryTest(SafeTestCase):
    """
    Test suite for the rest api client factory helper
    """

    def tearDown(self):
        """
        Ensure client is cleared after each test
        """
        super().tearDown()
        rac.REST_API_CLIENT = None

    def test_get_rest_api_client_returns_singleton_instance(self):
        """
        Ensure factory returns the same RestApiClient instance across calls
        """
        first_client = get_rest_api_client()
        second_client = get_rest_api_client()

        self.assertIsInstance(first_client, RestApiClient)
        self.assertIs(first_client, second_client)


class RestApiClientTokenTest(SafeTestCase):
    """
    Test suite covering RestApiClient authentication token behavior
    """

    def tearDown(self):
        """
        Ensure global client cache is reset after each test
        """
        super().tearDown()
        rac.REST_API_CLIENT = None

    def test_token_fetches_new_token_when_missing(self):
        """
        Should fetch a new token when none is cached or it is expired
        """
        client = get_rest_api_client()
        client._token = {}
        fresh_token = {'access_token': 'fresh-token'}

        with patch.object(client, '_get_new_token', return_value=fresh_token) as patched_get_new_token:
            with patch.object(client, 'get_exp', return_value=0):
                token = client.token

        self.assertEqual(token, fresh_token)
        self.assertEqual(client._token, fresh_token)
        patched_get_new_token.assert_called_once_with()

    def test_token_refreshes_when_near_expiration(self):
        """
        Should refresh the token when its expiration is within one minute
        """
        client = get_rest_api_client()
        client._token = {'access_token': 'stale-token'}
        refreshed_token = {'access_token': 'refreshed-token'}
        soon_expiring = datetime.now(timezone.utc).timestamp() + 30

        with patch.object(client, 'get_exp', return_value=soon_expiring):
            with patch.object(client, '_get_new_token', return_value=refreshed_token) as patched_get_new_token:
                token = client.token

        self.assertEqual(token, refreshed_token)
        self.assertEqual(client._token, refreshed_token)
        patched_get_new_token.assert_called_once_with()

    def test_token_returns_cached_when_expiration_is_far(self):
        """
        Should reuse cached token when expiration is more than one minute away
        """
        client = get_rest_api_client()
        cached_token = {'access_token': 'cached-token'}
        client._token = cached_token.copy()
        far_future_exp = datetime.now(timezone.utc).timestamp() + 6000

        with patch.object(client, 'get_exp', return_value=far_future_exp):
            with patch.object(client, '_get_new_token') as patched_get_new_token:
                token = client.token

        self.assertEqual(token, cached_token)
        self.assertIs(client._token, token)
        patched_get_new_token.assert_not_called()

    def test_get_exp_returns_exp_claim_from_jwt(self):
        """
        Should return the exp claim from decoded JWT payload
        """
        client = get_rest_api_client()
        expected_exp = datetime.now(timezone.utc).timestamp() + 123
        client._token = {'access_token': 'jwt-token'}

        with patch('ecodev_core.rest_api_client.jwt.decode', return_value={'exp': expected_exp}) as patched_decode:
            exp = client.get_exp()

        self.assertEqual(exp, expected_exp)
        patched_decode.assert_called_once_with('jwt-token', SECRET_KEY, algorithms=[ALGO])


    def test_get_exp_falls_back_to_current_timestamp_on_decode_failure(self):
        """
        Should fallback to current timestamp when JWT decoding fails
        """
        client = get_rest_api_client()
        client._token = {'access_token': 'invalid-token'}
        fixed_now = datetime(2025, 1, 1, tzinfo=timezone.utc)
        expected_timestamp = fixed_now.timestamp()

        with patch('ecodev_core.rest_api_client.jwt.decode', side_effect=Exception('decode failure')) as patched_decode:
            with patch('ecodev_core.rest_api_client.datetime') as patched_datetime:
                patched_datetime.now.return_value = fixed_now
                exp = client.get_exp()

        self.assertEqual(exp, expected_timestamp)
        patched_decode.assert_called_once_with()


class RestApiClientRequestTest(SafeTestCase):
    """
    Test suite checking HTTP helpers invoke header generation
    """
    def tearDown(self):
        """
        Ensure cached client cleared after each test
        """
        super().tearDown()
        rac.REST_API_CLIENT = None

    def test_get_header_uses_token_property_for_authorization(self):
        """
        Ensure Authorization header uses token property value
        """
        client = get_rest_api_client()

        with patch.object(RestApiClient, 'token', new_callable=PropertyMock) as token_property:
            token_property.return_value = {'access_token': 'header-token'}
            headers = client._get_header()

        self.assertEqual(headers['Authorization'], 'Bearer header-token')
        token_property.assert_called_once_with(client)

    def test_http_methods_fetch_headers_before_request(self):
        """
        Ensure each HTTP method adds headers by calling _get_header
        """
        client = get_rest_api_client()
        expected_headers = {'Authorization': 'Bearer header-token'}
        http_methods = [
            ('get', {'url': 'http://example.com', 'params': {'a': 1}}),
            ('post', {'url': 'http://example.com', 'data': {'x': 1}, 'params': {'b': 2}}),
            ('put', {'url': 'http://example.com', 'data': {'x': 2}, 'params': {'c': 3}}),
            ('patch', {'url': 'http://example.com', 'data': {'x': 3}, 'params': {'d': 4}}),
            ('delete', {'url': 'http://example.com', 'params': {'e': 5}}),
            ]

        for method_name, kwargs in http_methods:
            with self.subTest(method=method_name):
                with patch.object(client, '_get_header', return_value=expected_headers) as header_mock, \
                        patch('ecodev_core.rest_api_client.requests') as requests_module, \
                        patch('ecodev_core.rest_api_client.handle_response'):
                    request_callable = getattr(requests_module, method_name)
                    getattr(client, method_name)(**kwargs)

                header_mock.assert_called_once_with()
                request_callable.assert_called_once()
                self.assertEqual(request_callable.call_args.kwargs['headers'], expected_headers)

    def test_handle_response_returns_json_payload(self):
        """
        Ensure handle_response returns JSON body when request succeeds
        """
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.return_value = {'data': True}

        payload = handle_response(response)

        self.assertEqual(payload, {'data': True})
        response.raise_for_status.assert_called_once_with()

    def test_handle_response_raises_http_error(self):
        """
        Ensure HTTP errors are logged and re-raised
        """
        response = MagicMock(status_code=500, text='error')
        response.raise_for_status.side_effect = requests.HTTPError('server error')

        with self.assertRaises(requests.HTTPError):
            handle_response(response)

    def test_handle_response_raises_on_json_parsing_failure(self):
        """
        Ensure JSON parsing failures are logged and propagated
        """
        response = MagicMock()
        response.raise_for_status.return_value = None
        response.json.side_effect = ValueError('bad json')

        with self.assertRaises(Exception):
            handle_response(response)
