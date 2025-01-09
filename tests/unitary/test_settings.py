"""
Module testing Dynamic Settings configuration class
"""
from pathlib import Path

from ecodev_core import SafeTestCase
from ecodev_core import Settings

TEST_FOLDER = Path('/app/tests/unitary/data')


class SettingsTest(SafeTestCase):
    """
    Class testing Dynamic Settings configuration class
    """

    def test_create_settings(self):
        """
        test Dynamic Settings configuration class
        """
        settings = Settings(TEST_FOLDER)
        self.assertEqual(settings.super_secret, 'shhh')
        self.assertEqual(settings.xmas_fifth_day.partridges.another_super_secret, 'no i wont tell')
