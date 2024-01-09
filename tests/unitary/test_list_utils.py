"""
Module testing list utils methods
"""
from ecodev_core import first_or_default
from ecodev_core import first_transformed_or_default
from ecodev_core import group_by_value
from ecodev_core import lselect
from ecodev_core import lselectfirst
from ecodev_core import SafeTestCase


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
