"""
Module testing safe conversion methods
"""
from datetime import datetime

import numpy as np

from ecodev_core import boolify
from ecodev_core import datify
from ecodev_core import floatify
from ecodev_core import intify
from ecodev_core import safe_clt
from ecodev_core import SafeTestCase
from ecodev_core import SimpleReturn
from ecodev_core import stringify


@safe_clt
def safe_divide(a: int, b: int):
    """
    Safe test divide for testing purposes.
    """
    return a / b


class SafeConversionTest(SafeTestCase):
    """
    Class testing afe conversion methods
    """

    def test_floatify(self):
        """
        test floatify behaviour
        """
        self.assertEqual(floatify(3), 3.0)
        self.assertEqual(floatify(np.nan), None)
        self.assertEqual(floatify('toto'), None)
        self.assertEqual(floatify('3.0'), 3.0)

    def test_intify(self):
        """
        test intify behaviour
        """
        self.assertEqual(intify(3), 3)
        self.assertEqual(intify(np.nan), None)
        self.assertEqual(intify('toto'), None)
        self.assertEqual(intify('3'), 3)

    def test_stringify(self):
        """
        test stringify behaviour
        """
        self.assertEqual(stringify(3), '3')
        self.assertEqual(stringify(np.nan), None)
        self.assertEqual(stringify('toto'), 'toto')
        self.assertEqual(stringify('3'), '3')

    def test_boolify(self):
        """
        test boolify behaviour
        """
        self.assertEqual(boolify('true'), True)
        self.assertEqual(boolify('yes'), True)
        self.assertEqual(boolify('True'), True)
        self.assertEqual(boolify('Yes'), True)
        self.assertEqual(boolify('false'), False)
        self.assertEqual(boolify('no'), False)
        self.assertEqual(boolify('False'), False)
        self.assertEqual(boolify('No'), False)
        self.assertEqual(boolify(np.nan), None)
        self.assertEqual(boolify(True), True)
        self.assertEqual(boolify(False), False)
        self.assertEqual(boolify('toto'), None)
        self.assertEqual(boolify(3), None)
        self.assertEqual(boolify(None), None)

    def test_datify(self):
        """
        test datify behaviour
        """
        self.assertEqual(datetime(2024, 9, 2), datify('2024-09-02', '%Y-%m-%d'))
        self.assertTrue(datify('2024-09', '%Y-%m-%d') is None)

    def test_safe_clt(self):
        """
        Test that safe wrapper is working as intended.
        """
        self.assertEqual(safe_divide(1, 2), SimpleReturn(success=True, error=None))
        self.assertEqual(safe_divide(1, 0), SimpleReturn(success=False, error='division by zero'))
