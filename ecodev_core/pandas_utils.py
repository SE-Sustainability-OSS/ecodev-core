"""
Module implementing some utilitary methods on pandas types
"""
import tempfile
from base64 import b64decode
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import Optional

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


def get_excelfile(contents: str) -> pd.ExcelFile:
    """
    Function which converts user xlsx file upload into a pd.ExcelFile
    """
    content_type, content_string = contents.split(',')
    xl = b64decode(content_string)
    return pd.ExcelFile(xl)


def safe_drop_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """
    Returns a DataFrame without a list of columns, with a prior check on the existence of these
    columns in the DataFrame
    """

    return df.drop(columns=[col for col in columns if col in df.columns])


def is_null(value: Any) -> bool:
    """
    Checks if a value is null or not
    """
    return value is None or isinstance(value, float) and np.isnan(value)


def get_value(column: str, method: Callable, row: pd.Series) -> Optional[Any]:
    """
    Function which performs a method on a value if the column name is in the row index
    """
    if column not in row.index or is_null(row[column]):
        return None

    return method(row[column])
