"""
Module testing low-level read-write methods
"""
from pathlib import Path

from ecodev_core import load_json_file
from ecodev_core import make_dir
from ecodev_core import SafeTestCase
from ecodev_core import write_json_file


TEST_DIR = Path('/app/tests/unitary/test')


class ReadWriteTest(SafeTestCase):
    """
    Class testing low-level read-write methods
    """

    def setUp(self):
        """
        Class set up
        """
        super().setUp()
        self.directories_created.append(TEST_DIR)

    def test_read_write(self):
        """
        test low-level read-write methods
        """
        data = {'toto': 23}
        make_dir(TEST_DIR)
        write_json_file(data, TEST_DIR / 'test.json')
        loaded_data = load_json_file(TEST_DIR / 'test.json')
        self.assertEqual(data, loaded_data)
