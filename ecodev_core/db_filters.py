"""
Low level db filtering methods
"""
from datetime import datetime
from enum import Enum
from enum import unique
from typing import Callable
from typing import Dict

from sqlalchemy import func
from sqlalchemy.orm.attributes import InstrumentedAttribute
from sqlmodel import col
from sqlmodel.sql.expression import Select
from sqlmodel.sql.expression import SelectOfScalar

SelectOfScalar.inherit_cache = True  # type: ignore
Select.inherit_cache = True  # type: ignore
OPERATORS = ['>=', '<=', '!=', '=', '<', '>', 'contains ']


@unique
class ServerSideFilter(str, Enum):
    """
    All possible server side filtering mechanisms
    """
    STARTSTR = 'start_str'
    ILIKESTR = 'ilike_str'
    STRICTSTR = 'strict_str'
    LIKESTR = 'like_str'
    BOOL = 'bool'
    NUM = 'num'


def _filter_start_str_field(field: InstrumentedAttribute,
                            query: SelectOfScalar,
                            operator: str,
                            value: str
                            ) -> SelectOfScalar:
    """
    Add filter to the passed query for a str like field. The filtering is done by checking if
     the passed value starts the field.

    NB: case-insensitive!
    """
    return query.where(func.lower(col(field)).startswith(value.lower())) if value else query


def _filter_str_ilike_field(field: InstrumentedAttribute,
                            query: SelectOfScalar,
                            operator: str,
                            value: str
                            ) -> SelectOfScalar:
    """
    Add filter to the passed query for a str like field. The filtering is done by checking if
     the passed value is contained in db values

    NB: case-insensitive!
    """
    return query.where(col(field).ilike(f'%{value}%')) if value else query


def _filter_str_like_field(field: InstrumentedAttribute,
                           query: SelectOfScalar,
                           operator: str,
                           value: str
                           ) -> SelectOfScalar:
    """
    Add filter to the passed query for a str like field. The filtering is done by checking if
     the passed value is contained in db values
    """
    return query.where(col(field).contains(value)) if value else query


def _filter_strict_str_field(field: InstrumentedAttribute,
                             query: SelectOfScalar,
                             operator: str,
                             value: str
                             ) -> SelectOfScalar:
    """
    Add filter to the passed query for a strict str equality matching.
    The filtering is done by checking if the passed value is equal to one of the db values
    """
    return query.where(col(field) == value) if value else query


def _filter_bool_like_field(field: InstrumentedAttribute,
                            query: SelectOfScalar,
                            operator: str,
                            value: str
                            ) -> SelectOfScalar:
    """
    Add filter to the passed query for a bool like field. The filtering is done by comparing
     the passed value to db values
    """
    return query.where(col(field) == value) if value else query


def _filter_num_like_field(field: InstrumentedAttribute,
                           query: SelectOfScalar,
                           operator: str,
                           value: str,
                           is_date: bool = False
                           ) -> SelectOfScalar:
    """
    Add filter to the passed query for a num like (even datetime in case where is_date
    is set to True) field. The filtering is done by comparing the passed value to db values
    with the passed operator.
    """
    if not operator or not value:
        return query

    if operator == '>=':
        query = query.where(col(field) >= (_date(value) if is_date else float(value)))
    elif operator == '<=':
        query = query.where(col(field) <= (_date(value) if is_date else float(value)))
    elif operator == '!=':
        query = query.where(col(field) != (_date(value) if is_date else float(value)))
    elif operator == '=':
        query = query.where(col(field) == (_date(value) if is_date else float(value)))
    elif operator == '>':
        query = query.where(col(field) > (_date(value) if is_date else float(value)))
    elif operator == '<':
        query = query.where(col(field) < (_date(value) if is_date else float(value)))

    return query


SERVER_SIDE_FILTERS: Dict[ServerSideFilter, Callable] = {
    ServerSideFilter.STARTSTR: _filter_start_str_field,
    ServerSideFilter.STRICTSTR: _filter_strict_str_field,
    ServerSideFilter.LIKESTR: _filter_str_like_field,
    ServerSideFilter.ILIKESTR: _filter_str_ilike_field,
    ServerSideFilter.BOOL: _filter_bool_like_field,
    ServerSideFilter.NUM: _filter_num_like_field
}


def _date(year: str) -> datetime:
    """
    Convert the passed str year to a datetime to allow filtering on datetime years.
    """
    return datetime(year=int(year), month=1, day=1)
