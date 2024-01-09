"""
Module testing custom equal
"""
from ecodev_core import custom_equal
from ecodev_core import SafeTestCase


class CustomEqualTest(SafeTestCase):
    """
    Class testing custom equal
    """

    def test_custom_equal_float(self):
        """
        test custom equal float equality
        """

        self.assertTrue(custom_equal(3.0, 2.99999999999999, float))

    def test_custom_equal_str(self):
        """
        test custom equal str equality
        """
        self.assertTrue(custom_equal('3.0', '3.0', str))

    def test_custom_equal_none(self):
        """
        test custom equal none equality
        """
        self.assertTrue(custom_equal(None, None, str))

    def test_different_type_str(self):
        """
        test custom equal different type inequality
        """
        self.assertFalse(custom_equal('3.0', 3.0, str))
