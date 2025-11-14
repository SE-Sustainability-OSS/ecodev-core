"""
Module testing the package's rest api client
"""
from datetime import datetime
from datetime import timezone
from unittest.mock import patch

from ecodev_core import SafeTestCase
import ecodev_core.rest_api_client as rac
from ecodev_core import get_rest_api_client


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
        first_client = rac.get_rest_api_client()
        second_client = rac.get_rest_api_client()

        self.assertIsInstance(first_client, rac.RestApiClient)
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
        patched_decode.assert_called_once_with('jwt-token', rac.SECRET_KEY, algorithms=[rac.ALGO])


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
