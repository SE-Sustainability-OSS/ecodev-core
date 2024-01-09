"""
Module testing db interaction
"""
from sqlmodel import select
from sqlmodel import Session

from ecodev_core import AppRight
from ecodev_core import AppUser
from ecodev_core import create_db_and_tables
from ecodev_core import delete_table
from ecodev_core import engine
from ecodev_core import SafeTestCase


class DbConnectionTest(SafeTestCase):
    """
    Class testing some functions used in DB retrievers
    """

    def setUp(self):
        """
        Class testing db interaction
        """
        super().setUp()
        create_db_and_tables(AppUser)
        delete_table(AppRight)
        delete_table(AppUser)

    def test_db_connection(self):
        """
        Test db interaction
        """
        with Session(engine) as session:
            session.bulk_insert_mappings(AppUser, [{'user': 'user', 'password': 'password'}])
            db_users = session.exec(select(AppUser)).all()

        self.assertEqual(len(db_users), 1)
        delete_table(AppUser)
        with Session(engine) as session:
            db_users_2 = session.exec(select(AppUser)).all()
        self.assertEqual(len(db_users_2), 0)
