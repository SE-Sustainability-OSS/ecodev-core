"""
Module comparing whether two elements are both None or both not None and equals
"""
from typing import Optional

import numpy as np


def custom_equal(element_1: Optional[object], element_2: Optional[object], element_type: type):
    """
    Compare whether two elements are both None or both not None and equals (same type/same value)

    Args:
        element_1: the first element of the comparison
        element_2:  the second element of the comparison
        element_type:  the expected element type for both elements

    Returns:
        True if both None or both not None and equals (same type/same value)
    """
    if element_1 is None:
        return element_2 is None

    if not isinstance(element_1, element_type) or not isinstance(element_2, element_type):
        return False

    return np.isclose(element_1, element_2) if element_type == float else element_1 == element_2
