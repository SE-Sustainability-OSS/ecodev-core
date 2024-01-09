"""
Module testing filtering methods
"""
from datetime import datetime
from pathlib import Path

from sqlmodel import select
from sqlmodel import Session

from ecodev_core import AppActivity
from ecodev_core import AppRight
from ecodev_core import AppUser
from ecodev_core import create_db_and_tables
from ecodev_core import delete_table
from ecodev_core import engine
from ecodev_core import SafeTestCase
from ecodev_core import select_user
from ecodev_core import upsert_app_users
from ecodev_core.db_filters import _filter_bool_like_field
from ecodev_core.db_filters import _filter_num_like_field
from ecodev_core.db_filters import _filter_start_str_field
from ecodev_core.db_filters import _filter_str_ilike_field
from ecodev_core.db_filters import _filter_str_like_field
from ecodev_core.db_filters import _filter_strict_str_field


DATA_DIR = Path('/app/tests/unitary/data')


class FilterTest(SafeTestCase):
    """
    Class testing filtering methods
    """

    def setUp(self):
        """
        Class set up
        """
        super().setUp()
        create_db_and_tables(AppUser)
        delete_table(AppUser)
        delete_table(AppActivity)
        delete_table(AppRight)
        with Session(engine) as session:
            upsert_app_users(DATA_DIR / 'users.json', session)
            session.add(AppActivity(user='toto', application='toto', method='test'))
            session.commit()
        self.query_user = select(AppUser)
        self.query_activity = select(AppActivity)

    def test_start_str_field(self):
        """
        test _filter_start_str_field
        """
        filtered_query = _filter_start_str_field(AppUser.user, self.query_user,
                                                 operator='', value='adm')
        with Session(engine) as session:
            result = session.exec(filtered_query).all()
            self.assertEqual(len(result), 1)

    def test_filter_str_ilike_field(self):
        """
        test _filter_str_ilike_field
        """
        filtered_query = _filter_str_ilike_field(AppUser.user, self.query_user,
                                                 operator='', value='DM')
        with Session(engine) as session:
            result = session.exec(filtered_query).all()
        self.assertEqual(len(result), 1)

    def test_filter_strict_str_field(self):
        """
        test _filter_strict_str_field
        """
        filtered_query = _filter_str_like_field(AppUser.user, self.query_user,
                                                operator='', value='DM')
        filtered_query_1 = _filter_strict_str_field(AppUser.user, self.query_user,
                                                    operator='', value='admi')
        filtered_query_2 = _filter_strict_str_field(AppUser.user, self.query_user,
                                                    operator='', value='admin')
        with Session(engine) as session:
            result = session.exec(filtered_query).all()
            result_1 = session.exec(filtered_query_1).all()
            result_2 = session.exec(filtered_query_2).all()
        self.assertEqual(len(result), 0)
        self.assertEqual(len(result_1), 0)
        self.assertEqual(len(result_2), 1)

    def test_filter_bool_like_field(self):
        """
        test _filter_bool_like_field
        """
        filtered_query = _filter_bool_like_field(AppUser.user, self.query_user,
                                                 operator='', value='true')
        with Session(engine) as session:
            result = session.exec(filtered_query).all()
        self.assertEqual(len(result), 0)

    def test_filter_num_like_field(self):
        """
        test _filter_num_like_field
        """
        filtered_date_1 = _filter_num_like_field(AppActivity.created_at, self.query_activity,
                                                 operator='>=',
                                                 value=datetime.now().year, is_date=True)
        filtered_date_2 = _filter_num_like_field(AppActivity.created_at, self.query_activity,
                                                 operator='>',
                                                 value=datetime.now().year, is_date=True)
        filtered_date_3 = _filter_num_like_field(AppActivity.created_at, self.query_activity,
                                                 operator='<=',
                                                 value=datetime.now().year+1, is_date=True)
        filtered_date_4 = _filter_num_like_field(AppActivity.created_at, self.query_activity,
                                                 operator='<',
                                                 value=datetime.now().year+1, is_date=True)
        filtered_date_5 = _filter_num_like_field(AppActivity.created_at, self.query_activity,
                                                 operator='=',
                                                 value=datetime.now().year, is_date=True)
        with Session(engine) as session:
            admin = select_user('admin', session)
            filtered_query_equal = _filter_num_like_field(AppUser.id, self.query_user, operator='=',
                                                          value=admin.id)
            result = session.exec(filtered_query_equal).all()
            result_date_1 = session.exec(filtered_date_1).all()
            result_date_2 = session.exec(filtered_date_2).all()
            result_date_3 = session.exec(filtered_date_3).all()
            result_date_4 = session.exec(filtered_date_4).all()
            result_date_5 = session.exec(filtered_date_5).all()
        self.assertEqual(len(result), 1)
        self.assertEqual(len(result_date_1), 1)
        self.assertEqual(len(result_date_2), 1)
        self.assertEqual(len(result_date_3), 1)
        self.assertEqual(len(result_date_4), 1)
        self.assertEqual(len(result_date_5), 0)
