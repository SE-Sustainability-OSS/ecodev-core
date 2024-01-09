"""
Module implementing helper methods working on lists
"""
from enum import Enum
from typing import Type
from typing import Union

from ecodev_core.safe_utils import stringify


def enum_converter(field: Union[str, float],
                   enum_type: Type,
                   default: Union[Enum, None] = None
                   ) -> Union[Enum, None]:
    """
    Convert possibly None field to an enum_type if possible, return default otherwise
    """
    try:
        return enum_type(stringify(field))
    except ValueError:
        return default
