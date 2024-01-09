"""
Module implementing some utilitary methods on pandas types
"""
import tempfile
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd


def pd_equals(prediction: pd.DataFrame, gt_path=Path):
    """
    Since some Nones are serialized as Nans by pandas (heavy type inference),
     we store the prediction at a temporary location in order to reload it on the fly and compare it
     to a pre-store ground truth, in order that both gt and prediction benefited from the same
     type inferences.
    """
    with tempfile.TemporaryDirectory() as folder:
        prediction.to_csv(Path(folder) / 'tmp.csv', index=False)
        reloaded_prediction = pd.read_csv(Path(folder) / 'tmp.csv')
    pd.testing.assert_frame_equal(reloaded_prediction, pd.read_csv(gt_path))


def jsonify_series(row: pd.Series) -> Dict:
    """
    Convert a serie into a json compliant dictionary (replacing np.nans by Nones)
    """
    return {key: None if isinstance(value, float) and np.isnan(value) else value for key, value in
            row.to_dict().items()}
