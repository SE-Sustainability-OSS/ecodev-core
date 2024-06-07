"""
Module testing list utils methods
"""
from ecodev_core import first_or_default
from ecodev_core import first_transformed_or_default
from ecodev_core import group_by_value
from ecodev_core import lselect
from ecodev_core import lselectfirst
from ecodev_core import SafeTestCase
from ecodev_core.list_utils import first_func_or_default
from ecodev_core.list_utils import group_by
from ecodev_core.list_utils import sort_by_keys
from ecodev_core.list_utils import sort_by_values


class ListUtilsTest(SafeTestCase):
    """
    Class testing list utils methods
    """

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
