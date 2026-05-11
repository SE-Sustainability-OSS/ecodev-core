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


def _normalize_punct_for_enum_match(s: str) -> str:
    """Map typographic/Unicode dashes to ASCII hyphen so Excel-sourced labels match enum values."""
    t = str(s).strip()
    for ch in ('\u2010', '\u2011', '\u2012', '\u2013', '\u2014', '\u2212', '\u00ad'):
        t = t.replace(ch, '-')
    return t


def resolve_enum(raw: str, enum_cls: Type[Enum]) -> Enum:
    """Resolve a raw string to an enum member by comparing normalised, case-folded .values."""
    t_low = _normalize_punct_for_enum_match(raw).casefold()
    for m in enum_cls:
        if _normalize_punct_for_enum_match(str(m.value)).casefold() == t_low:
            return m
    raise ValueError(f'Unknown value {raw!r} for enum: {enum_cls.__name__}')
