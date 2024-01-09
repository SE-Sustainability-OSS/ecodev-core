"""
Module testing enum converter method
"""
from ecodev_core import enum_converter
from ecodev_core import Permission
from ecodev_core import SafeTestCase


class EnumConverterTest(SafeTestCase):
    """
    Class testing enum converter method
    """

    def test_enum_converter(self):
        """
        test enum_converter
        """
        self.assertEqual(enum_converter('Admin', Permission), Permission.ADMIN)
        self.assertTrue(enum_converter('toto', Permission) is None)
