"""
Module testing list utils methods
"""
from sqlmodel import select
from sqlmodel import Session

from ecodev_core import AppRight
from ecodev_core import AppUser
from ecodev_core import create_db_and_tables
from ecodev_core import delete_table
from ecodev_core import engine
from ecodev_core import first_or_default
from ecodev_core import first_transformed_or_default
from ecodev_core import group_by_value
from ecodev_core import lselect
from ecodev_core import lselectfirst
from ecodev_core import SafeTestCase
from ecodev_core.list_utils import first_func_or_default
from ecodev_core.list_utils import group_by
from ecodev_core.list_utils import list_tuple_to_dict
from ecodev_core.list_utils import sort_by_keys
from ecodev_core.list_utils import sort_by_values


class ListUtilsTest(SafeTestCase):
    """
    Class testing list utils methods
    """

    def setUp(self):
        """
        Class testing db interaction
        """
        super().setUp()
        create_db_and_tables(AppUser)
        delete_table(AppRight)
        delete_table(AppUser)

    def test_first_or_default(self):
        """
        test first_or_default method
        """
        data = [1, 2, 3, 1, 2, 3]
        self.assertEqual(first_or_default(data, lambda x: x > 2), 3)
        self.assertEqual(first_or_default(data), 1)
        self.assertEqual(first_or_default(None), None)

    def test_group_by_value(self):
        """
        test group_by_value method
        """
        data = [1, 2, 3, 1, 1, 2, 3]
        self.assertEqual(group_by_value(data), {1: [0, 3, 4], 2: [1, 5], 3: [2, 6]})

    def test_group_by(self):
        """
        Test custom group_by method
        """
        data = [1, 2, 3, 1, 1, 2, 3]
        for key, group in group_by(data, None):
            if key == 1:
                for _ in range(3):
                    self.assertCountEqual(group, [1, 1, 1])

    def test_lselect(self):
        """
        test lselect method
        """
        data = [1, 2, 3, 1, 1, 2, 3]
        self.assertEqual(lselect(data, lambda x: x > 2), [3, 3])
        self.assertEqual(lselectfirst(data, lambda x: x > 2), 3)

    def test_first_transformed_or_default(self):
        """
        test first_transformed_or_default method
        """
        data = [1, 2, 3, 1, 1, 2, 3]
        self.assertEqual(first_transformed_or_default(data, lambda x: x * 3 if x > 2 else None), 9)

    def test_first_func_or_default(self):
        """
        test first_func_or_default method
        """
        func_1, func_2, func_3 = lambda x: x - 5, lambda x: x ** 2 + 1, lambda x: x ** 3 + 2
        self.assertEqual(first_func_or_default([func_1, func_2, func_3], 7), 2)
        self.assertEqual(first_func_or_default([func_1, func_2, func_3], 3, lambda x: x > 0), 10)
        self.assertEqual(first_func_or_default([func_1, func_2, func_3], 7,
                                               lambda x: x < 0, 'Missed'), 'Missed')

    def test_sort_by_keys(self):
        """
        test sort_by_keys method
        """
        self.assertEqual(sort_by_keys({2: 3, 1: 1, 3: -1}), {1: 1, 2: 3, 3: -1})

    def test_sort_by_values(self):
        """
        test sort_by_values method
        """
        self.assertEqual(sort_by_values({2: 3, 1: 1, 3: -1}), {3: -1, 1: 1, 2: 3})

    def test_list_tuple_to_dict(self):
        """
        Test list_tuple_to_dict method
        """
        with Session(engine) as session:
            session.bulk_insert_mappings(AppUser, [{'user': 'user', 'password': 'password'}])
            users = list_tuple_to_dict(session.exec(select(AppUser.user, AppUser.password)).all())
            self.assertEqual(type(users), list)
            self.assertEqual(type(users[0]), dict)
            self.assertEqual(len(users), 1)
            self.assertEqual(users[0]['user'], 'user')
            self.assertEqual(users[0]['password'], 'password')
