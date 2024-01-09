"""
Module testing check dependencies behaviour
"""
import tempfile
from pathlib import Path

from ecodev_core import check_dependencies
from ecodev_core import compute_dependencies
from ecodev_core import SafeTestCase


TEST_DIR = Path('/app/tests/unitary/data')
CODE_DIR = TEST_DIR / 'code' / 'ecodev_core'


class DependencyTest(SafeTestCase):
    """
    Class testing check dependencies behaviour
    """

    def test_compute_dependency(self):
        """
        test compute dependency behaviour
        """
        with open(TEST_DIR / 'dependencies_app.txt', 'r') as f:
            ground_truth = f.read()
        with tempfile.TemporaryDirectory() as output_folder:
            compute_dependencies(CODE_DIR, Path(output_folder), plot=False)
            with open(Path(output_folder) / 'dependencies_ecodev_core.txt', 'r') as f:
                pred = f.read()
            self.assertEqual(ground_truth, pred)

    def test_check_dependency(self):
        """
        test that expected dependencies are rightly checked
        """
        self.assertTrue(check_dependencies(CODE_DIR, TEST_DIR / 'dependencies_app.txt'))

    def test_wrong_check_dependency(self):
        """
        test that changed dependencies are rightly NOT checked
        """
        self.assertFalse(check_dependencies(CODE_DIR, TEST_DIR / 'wrong_dependencies_app.txt'))
