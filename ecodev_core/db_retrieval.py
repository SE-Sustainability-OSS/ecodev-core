"""
Low level methods to retrieve data from db in a paginated way
"""
from math import ceil
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

import pandas as pd
from sqlalchemy import func
from sqlmodel import col
from sqlmodel import or_
from sqlmodel import select
from sqlmodel import Session
from sqlmodel.sql.expression import Select
from sqlmodel.sql.expression import SelectOfScalar

from ecodev_core.db_connection import engine
from ecodev_core.db_filters import SERVER_SIDE_FILTERS
from ecodev_core.db_filters import ServerSideFilter
from ecodev_core.list_utils import first_or_default
from ecodev_core.pydantic_utils import Frozen

SelectOfScalar.inherit_cache = True  # type: ignore
Select.inherit_cache = True  # type: ignore
OPERATORS = ['>=', '<=', '!=', '=', '<', '>', 'contains ']


class ServerSideField(Frozen):
    """
    Simple class used for sever side data retrieval

    Attributes are:
        - col_name: the name as it will appear on the frontend interface
        - field_name: the SQLModel attribute name associated with this field
        - field: the SQLModel attribute associated with this field
        - filter: the filtering mechanism to use for this field
    """
    col_name: str
    field_name: str
    field: Any = None
    filter: ServerSideFilter


def count_rows(fields: List[ServerSideField],
               model: Any,
               limit: Union[int, None] = None,
               filter_str: str = '',
               search_str: str = '',
               search_cols: Optional[List] = None) -> int:
    """
    Count the total number of rows in the db model, with statically defined field_filters fed with
    dynamically set frontend filters. Divide this total number by limit to account for pagination.
    """
    with Session(engine) as session:
        count = session.exec(_get_full_query(fields, model, filter_str, True, search_str,
                                             search_cols)).one()

        return ceil(count / limit) if limit else count


def get_rows(fields: List[ServerSideField],
             model: Any,
             limit: Union[int, None] = None,
             offset: Union[int, None] = None,
             filter_str: str = '',
             search_str: str = '',
             search_cols: Optional[List] = None,
             fields_order: Optional[Callable] = None
             ) -> pd.DataFrame:
    """
    Select relevant row lines from model db. Select the whole db if no limit or offset is provided.
    Convert the rows to a dataframe in order to show the result in a dash data_table.

    NB:
    * 'fields_order' specify how to order the result rows
    * 'limit' and 'offset' correspond to the pagination of the results.
    * 'search_str' corresponds to the search string from the search input.
    """
    with Session(engine) as session:
        rows = _paginate_db_lines(fields, model, session, limit, offset, filter_str,
                                  search_str, search_cols, fields_order)
    if len(raw_df := pd.DataFrame.from_records([row.model_dump() for row in rows])) > 0:
        return raw_df.rename(columns={field.field_name: field.col_name for field in fields}
                             )[[field.col_name for field in fields]]
    return pd.DataFrame(columns=[field.col_name for field in fields])


def _paginate_db_lines(fields: List[ServerSideField],
                       model: Any,
                       session: Session,
                       limit: Union[int, None],
                       offset: Union[int, None],
                       filter_str: str,
                       search_str: str = '',
                       search_cols: Optional[List] = None,
                       fields_order: Optional[Callable] = None,
                       ) -> List:
    """
    Select relevant row lines from model db. Select the whole db if no limit or offset is provided.
    """
    if fields_order is None:
        fields_order = _get_default_field_order(fields)

    query = fields_order(_get_full_query(fields, model, filter_str, count=False,
                                         search_str=search_str, search_cols=search_cols))
    if limit is not None and offset is not None:
        return list(session.exec(query.offset(offset * limit).limit(limit)))
    return list(session.exec(query).all())


def _get_full_query(fields: List[ServerSideField],
                    model: Any,
                    filter_str: str,
                    count: bool = False,
                    search_str: str = '',
                    search_cols: Optional[List] = None
                    ) -> SelectOfScalar:
    """
    Forge a complete select query given both search and filter strings

    NB:
    * This relies on the passed statically defined field_filters corresponding to the model.
    * The field_filters are used jointly with the dynamically set frontend filters.

    """
    filter_query = _get_filter_query(fields, model, _get_frontend_filters(filter_str), count)

    if not search_str or not search_cols:
        return filter_query

    return filter_query.where(or_(col(field).ilike(f'%{search_str.strip()}%')
                                  for field in search_cols))


def _get_frontend_filters(raw_filters: str) -> Dict[str, Tuple[str, str]]:
    """
    Forge a dictionary of field keys, (operator, value) values in order to filter a db model.
    """
    split_filters = raw_filters.split(' && ')
    return {elt[elt.find('{') + 1: elt.rfind('}')]: _forge_filter(elt) for elt in split_filters}


def _forge_filter(elt: str) -> Tuple[str, str]:
    """
    Forge the operator and value associated to the passed element. Do so by scanning the ordered
    sequence of OPERATORS and returning the first matching (value is on the right of it).
    """
    return next(((key, elt.split(key)[-1]) for key in OPERATORS if key in elt), ('', ''))


def _get_filter_query(fields: List[ServerSideField],
                      model: Any,
                      frontend_filters: Dict[str, Tuple[str, str]],
                      count: bool = False
                      ) -> SelectOfScalar:
    """
    Filter a model given backend static field_filters called with dynamically set frontend_filters.

    Returns:
        * either the query fetching the filtered rows (count = False)
        * or the filter row count.
    """
    query = select(func.count(model.id)) if count else select(model)
    if not frontend_filters or not all(frontend_filters.keys()):
        return query

    for key, (operator, value) in frontend_filters.items():
        if field := first_or_default(fields, lambda x: x.col_name == key):
            query = SERVER_SIDE_FILTERS[field.filter](query=query, operator=operator,
                                                      value=value, field=field.field)

    return query


def _get_default_field_order(fields: List[ServerSideField]) -> Callable:
    """
    Recover default field order from list of fields
    """
    def fields_order(query):
        """
        Default field ordering

        Take the initial query as input and specify the order to use.
        """
        return query.order_by(*[field.field for field in fields])

    return fields_order
