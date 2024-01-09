"""
Module testing db retrieval/filtering methods
"""
from pathlib import Path

from sqlmodel import Session

from ecodev_core import AppRight
from ecodev_core import AppUser
from ecodev_core import count_rows
from ecodev_core import create_db_and_tables
from ecodev_core import delete_table
from ecodev_core import engine
from ecodev_core import get_rows
from ecodev_core import SafeTestCase
from ecodev_core import ServerSideField
from ecodev_core import ServerSideFilter
from ecodev_core import upsert_app_users


DATA_DIR = Path('/app/tests/unitary/data')
APP_FILTER = ServerSideField(col_name='user', field_name='field_name', field=AppUser.user,
                             filter=ServerSideFilter.ILIKESTR)


class DbRetrievalTest(SafeTestCase):
    """
    Class testing retrieval/filtering methods
    """

    def setUp(self):
        """
        Class set up
        """
        super().setUp()
        create_db_and_tables(AppUser)
        delete_table(AppRight)
        delete_table(AppUser)
        with Session(engine) as session:
            upsert_app_users(DATA_DIR / 'users.json', session)

    def test_get_rows(self):
        """
        test that the get_rows method works as intended
        """
        self.assertTrue(len(get_rows([APP_FILTER], AppUser)) == 3)
        self.assertTrue(len(get_rows([APP_FILTER], AppUser, filter_str='{user} scontains i')) == 3)
        self.assertTrue(len(get_rows([APP_FILTER], AppUser, limit=2, offset=0,
                                     filter_str='{user} scontains i')) == 2)
        self.assertTrue(len(get_rows([APP_FILTER], AppUser, limit=2, offset=1,
                                     filter_str='{user} scontains i')) == 1)

    def test_count_rows(self):
        """
        test that the count_rows method works as intended
        """
        self.assertTrue(count_rows([APP_FILTER], AppUser) == 3)
        self.assertTrue(count_rows([APP_FILTER], AppUser, filter_str='{user} scontains o') == 1)
