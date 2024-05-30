"""
Module testing low-level pandas utils methods
"""
from pathlib import Path

import numpy as np
import pandas as pd

from ecodev_core import intify
from ecodev_core import load_json_file
from ecodev_core import SafeTestCase
from ecodev_core.pandas_utils import get_excelfile
from ecodev_core.pandas_utils import get_value
from ecodev_core.pandas_utils import is_null
from ecodev_core.pandas_utils import jsonify_series
from ecodev_core.pandas_utils import pd_equals
from ecodev_core.pandas_utils import safe_drop_columns

TEST_FILE = Path('/app/tests/unitary/data/test_csv.csv')


class ReadWriteTest(SafeTestCase):
    """
    Class testing low-level pandas utils methods
    """

    def test_panda_equals(self):
        """
        test pd_equals method (subtlety of None np.Nan that imposes to write on/read from disk)
        """
        df = pd.DataFrame.from_dict({'a': [1], 'b': None})
        self.assertTrue(pd_equals(df, TEST_FILE) is None)

    def test_jsonify_serie(self):
        """
        test jsonify_series (subtlety of None/np.Nan)
        """
        df = pd.DataFrame.from_dict({'a': [1, 2], 'b': [np.nan, 2]})
        self.assertDictEqual(jsonify_series(df['b']), {0: None, 1: 2.0})

    def test_get_excelfile(self):
        """
        Test get_excelfile utils method
        """
        xl = get_excelfile(load_json_file(TEST_FILE.parent / 'str_parsing.json')['data'])
        gt_df = pd.read_csv(TEST_FILE.parent / 'gt_str_parsing.csv')
        self.assertTrue(gt_df.equals(xl.parse('input')))

    def test_safe_drop_columns(self):
        """
        Test safe_drop_columns utils method
        """
        df = pd.DataFrame({'a': [1, 2, 3], 'b': [None, None, None]})

        self.assertIsNone(pd.testing.assert_frame_equal(safe_drop_columns(df, ['b']),
                                                        df.drop(columns='b')))
        self.assertIsNone(pd.testing.assert_frame_equal(safe_drop_columns(df, ['c']), df))

    def test_is_null(self):
        """
        test whether a value is null (both None and NaN)
        """
        self.assertTrue(is_null(None))
        self.assertTrue(is_null(np.nan))
        self.assertFalse(is_null(15))
        self.assertFalse(is_null('test'))

    def test_get_value(self):
        """
        Test get_value utils method
        """
        df = pd.DataFrame({'a': [1, 2, 3], 'b': [None, None, None]})

        self.assertEqual(get_value('a', intify, df.iloc[0]), 1)
        self.assertEqual(get_value('c', intify, df.iloc[0]), None)
