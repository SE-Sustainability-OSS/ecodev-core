"""
Module testing low-level pandas utils methods
"""
from pathlib import Path

import numpy as np
import pandas as pd

from ecodev_core import load_json_file
from ecodev_core import SafeTestCase
from ecodev_core.pandas_utils import get_excelfile
from ecodev_core.pandas_utils import jsonify_series
from ecodev_core.pandas_utils import pd_equals


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
