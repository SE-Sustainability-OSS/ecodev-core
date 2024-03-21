"""
Module testing authentication methods
"""
from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session

from ecodev_core import AppActivity
from ecodev_core import AppRight
from ecodev_core import AppUser
from ecodev_core import attempt_to_log
from ecodev_core import AUTH
from ecodev_core import create_db_and_tables
from ecodev_core import dash_monitor
from ecodev_core import delete_table
from ecodev_core import engine
from ecodev_core import fastapi_monitor
from ecodev_core import get_access_token
from ecodev_core import get_recent_activities
from ecodev_core import is_monitoring_user
from ecodev_core import SafeTestCase
from ecodev_core import select_user
from ecodev_core import upsert_app_users
from ecodev_core.authentication import _create_access_token
from ecodev_core.authentication import _hash_password
from ecodev_core.authentication import _verify_access_token
from ecodev_core.authentication import ADMIN_ERROR
from ecodev_core.authentication import get_app_services
from ecodev_core.authentication import get_current_user
from ecodev_core.authentication import get_user
from ecodev_core.authentication import INVALID_CREDENTIALS
from ecodev_core.authentication import INVALID_TFA
from ecodev_core.authentication import INVALID_USER
from ecodev_core.authentication import is_admin_user
from ecodev_core.authentication import is_authorized_user
from ecodev_core.authentication import JwtAuth
from ecodev_core.authentication import MONITORING_ERROR
from ecodev_core.authentication import safe_get_user
from ecodev_core.authentication import TokenData


DATA_DIR = Path('/app/tests/unitary/data')


class AuthenticationTest(SafeTestCase):
    """
    Class testing authentication methods
    """

    def setUp(self):
        """
        Class set up
        """
        super().setUp()
        create_db_and_tables(AppUser)
        delete_table(AppActivity)
        delete_table(AppRight)
        delete_table(AppUser)
        with Session(engine) as session:
            upsert_app_users(DATA_DIR / 'users.json', session)
            client = select_user('client', session)
            client.rights = [AppRight(app_service='demo')]
            session.commit()

    def test_access_token(self):
        """
        test that access_token method is working as intended.
        """
        self.assertTrue(get_access_token({}) is None)
        with Session(engine) as session:
            valid_token = get_access_token({'token': attempt_to_log('client', 'client', session)})
            self.assertTrue(len(valid_token) > 10)

    def test_monitoring_user(self):
        """
        Test that is_monitoring_user check is working as intended.
        """
        try:
            wrong_monito = is_monitoring_user('toto')
        except HTTPException as e:
            wrong_monito = e.detail
        self.assertEqual(wrong_monito, INVALID_CREDENTIALS)

        try:
            with Session(engine) as session:
                client_token = attempt_to_log('client', 'client', session)
            wrong_monito = is_monitoring_user(get_access_token({'token': client_token}))
        except HTTPException as e:
            wrong_monito = e.detail
        self.assertEqual(wrong_monito, MONITORING_ERROR)

        with Session(engine) as session:
            token = attempt_to_log('monitoring', 'monitoring', session)
        monito = is_monitoring_user(get_access_token({'token': token}))
        self.assertEqual(monito.user, 'monitoring')
        self.assertTrue(isinstance(monito, AppUser))

    def test_monitoring(self):
        """
        Test that monitoring fastapi or dash entrypoint works
        """
        with Session(engine) as session:
            token = attempt_to_log('monitoring', 'monitoring', session)
            monito = is_monitoring_user(get_access_token({'token': token}))
            fastapi_monitor('fastapi', monito, 'test', session)
            dash_monitor('dash', {'token': token}, 'test')
            monitored = get_recent_activities('2024/1/1', session)
        self.assertEqual((len(monitored)), 2)

    def test_http_errors(self):
        """
        Test http error messages
        """
        with Session(engine) as session:
            try:
                wrong_pass = attempt_to_log('client', 'clien', session)
            except HTTPException as e:
                wrong_pass = e.detail
            self.assertEqual(wrong_pass, INVALID_CREDENTIALS)

            try:
                wrong_user = attempt_to_log('clien', 'clien', session)
            except HTTPException as e:
                wrong_user = e.detail
            self.assertEqual(wrong_user, INVALID_USER)

    def test_app_rights(self):
        """
        Test app_services from app_rights retrieval works as intended.
        """
        with Session(engine) as session:
            services = get_app_services(select_user('client', session), session)
            admin_services = get_app_services(select_user('admin', session), session)
        self.assertCountEqual(services, ['demo'])
        self.assertCountEqual(admin_services, [])

    def test_jwtauth(self):
        """
        Test JwtAuth authorization mechanism
        """
        auth = JwtAuth(AUTH.secret_key)
        self.assertTrue(auth.authorized({'username': 'client', 'password': 'client'}) is None)
        self.assertTrue(len(auth.authorized({'username': 'admin', 'password': 'admin'})) > 0)

    def test_standard_auth(self):
        """
        Test that regular authentication works as expected
        """
        with Session(engine) as session:
            client_token = get_access_token({'token': attempt_to_log('client', 'client', session)})
        self.assertTrue(is_authorized_user(client_token))
        self.assertFalse(is_authorized_user('toto'))

        try:
            wrong = get_user('toto')
        except HTTPException as e:
            wrong = e.detail
        self.assertEqual(wrong, INVALID_CREDENTIALS)

        client = get_current_user(client_token)
        self.assertEqual(client.user, 'client')
        self.assertTrue(isinstance(client, AppUser))

        try:
            wrong_tfa = get_current_user(client_token, '123456')
        except HTTPException as e:
            wrong_tfa = e.detail
        self.assertEqual(wrong_tfa, INVALID_TFA)

    def test_safe_get_user(self):
        """
        Test that safe user retrieval works as expected
        """
        with Session(engine) as session:
            token = {'token': attempt_to_log('client', 'client', session)}
        client = safe_get_user(token)
        self.assertEqual(client.user, 'client')
        self.assertTrue(isinstance(client, AppUser))

        wrong = safe_get_user({'token': 'toto'})
        self.assertTrue(wrong is None)

    def test_jwt_encode_decode(self):
        """
        Test jwd encoding and decoding mechanism
        """
        token = _create_access_token({'user_id': 1}, tfa_value='123456')
        self.assertTrue(_verify_access_token(token, '123456') == TokenData(id=1))

        try:
            wrong_tfa = _verify_access_token(token, '123455')
        except HTTPException as e:
            wrong_tfa = e.detail
        self.assertEqual(wrong_tfa, INVALID_TFA)

    def test_admin_auth(self):
        """
        Test that admin authentication works as expected
        """
        with Session(engine) as session:
            client_token = get_access_token({'token': attempt_to_log('client', 'client', session)})
            admin_token = get_access_token({'token': attempt_to_log('admin', 'admin', session)})

        try:
            wrong = is_admin_user('toto')
        except HTTPException as e:
            wrong = e.detail
        self.assertEqual(wrong, INVALID_CREDENTIALS)

        try:
            wrong_user = is_admin_user(client_token)
        except HTTPException as e:
            wrong_user = e.detail
        self.assertEqual(wrong_user, ADMIN_ERROR)

        admin = is_admin_user(admin_token)
        self.assertEqual(admin.user, 'admin')
        self.assertTrue(isinstance(admin, AppUser))

    def test_hash_password(self):
        """
        Test that hashing indeed change the password, and thanks to salt two successive hashing
        still give a different hash.
        """
        hash_1, hash_2 = _hash_password('toto'), _hash_password('toto')
        self.assertFalse(hash_1 == 'toto')
        self.assertFalse(hash_1 == hash_2)
