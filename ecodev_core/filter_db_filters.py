"""
Low level methods to retrieve data from db in a paginated way, using a filter model
"""
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional

from ecodev_core import engine
from ecodev_core import logger_get
from ecodev_core import ServerSideField
from ecodev_core import ServerSideFilter
from ecodev_core.db_filters import SERVER_SIDE_FILTERS
from sqlalchemy import func
from sqlalchemy.orm import InstrumentedAttribute
from sqlmodel import col
from sqlmodel import or_
from sqlmodel import select
from sqlmodel import Session
from sqlmodel.sql.expression import SelectOfScalar

log = logger_get(__name__)


def count_rows(
        model: Any,
        filter_model: Optional[Dict],
        search_str: str = '',
        search_cols: Optional[List] = None,
) -> int:
    """
    Count the total number of rows, with reference to a filtering model
    """
    full_query = _get_full_query(
        model=model,
        filter_model=filter_model,
        start_row=None,
        end_row=None,
        search_str=search_str,
        search_cols=search_cols,
        fields_order=None,
        count=True
    )

    with Session(engine) as session:
        return session.exec(full_query).one()


def get_rows(
        model: Any,
        filter_model: Optional[Dict],
        start_row: Optional[int] = None,
        end_row: Optional[int] = None,
        search_str: str = '',
        search_cols: Optional[List] = None,
        fields_order: Optional[Callable] = None,
) -> List[Dict[str, Any]]:
    """
    Select relevant row lines from model db based on provided filter model.

    Breaking change from previous version:
    * filter_str is removed
    * Keeps the column names from the database (separate front and back)
    * does not use Pandas
    * no filtering of columns (in particular: no argument 'fields')

    NB:
    * Select the whole db if no start_row or end_row is provided.
    * 'fields_order' specify how to order the result rows
    * 'search_str' corresponds to the search string from the search input.

    """
    full_query = _get_full_query(
        model=model,
        filter_model=filter_model,
        start_row=start_row,
        end_row=end_row,
        search_str=search_str,
        search_cols=search_cols,
        fields_order=fields_order,
        count=False
    )

    with Session(engine) as session:
        data_list = [row.model_dump() for row in session.exec(full_query).all()]

    return data_list


def get_unique_values(
        model: Any,
        fields_to_query: List[str],
        filter_model: Optional[Dict],
        search_str: str = '',
        search_cols: Optional[List] = None,
) -> Dict[str, List[Any]]:
    """
    Retrieve all unique values from fields in the fields_to_query

    NB: filters according to filter_model, search_str and the associated search_cols

    returns: dictionary[field_name, list of unique values]
    """
    with Session(engine) as session:
        return {
            field: list(
                session.exec(
                    _get_full_query(
                        model=getattr(model, field),
                        filter_model=filter_model,
                        search_str=search_str,
                        search_cols=search_cols,
                        unique=True
                    )
                )
            )
            for field in fields_to_query
        }


def _get_full_query(
        model: Any,
        filter_model: Optional[Dict],
        start_row: Optional[int] = None,
        end_row: Optional[int] = None,
        search_str: str = '',
        search_cols: Optional[List] = None,
        fields_order: Optional[Callable] = None,
        count: bool = False,
        unique: bool = False
) -> SelectOfScalar:
    """
    Get full query with order and pagination, ready for execution
    """
    return _paginate_query(
        _order_query(
            _add_search_query(
                _filter_model_query(
                    query=_get_select_query(model, count, unique),
                    filter_model=filter_model,
                    model=model
                ),
                search_str=search_str, search_cols=search_cols
            ),
            fields_order=fields_order
        ),
        start_row=start_row, end_row=end_row
    )


def _get_select_query(
        model: Any,
        count: bool = False,
        unique: bool = False
) -> SelectOfScalar:
    """
    Get the basic select query
    """
    if count:
        return select(func.count(model.id))

    if unique:
        return select(model).group_by(model)

    return select(model)


def _add_search_query(query: SelectOfScalar, search_str: str = '',
                      search_cols: Optional[List] = None) -> SelectOfScalar:
    """
    Add the search query to the existing query
    """
    if not search_str or not search_cols:
        return query

    return query.where(or_(col(field).ilike(f'%{search_str.strip()}%') for field in search_cols))


def _order_query(query: SelectOfScalar, fields_order: Optional[Callable] = None) -> SelectOfScalar:
    """
    Order the results of the search query
    """
    if not fields_order:
        return query

    return query


def _paginate_query(query: SelectOfScalar, start_row: Optional[int] = None,
                    end_row: Optional[int] = None) -> SelectOfScalar:
    """
    Paginate results according to provided args
    """
    if start_row is None or end_row is None:
        return query

    return query.offset(start_row).limit(end_row - start_row)


def _filter_columns(fields: List[ServerSideField], data_list: List[Dict[str, Any]]
                    ) -> List[Dict[str, Any]]:
    """
    Keep only certain columns from the data
    """
    aux_list_cols = [ss_field.field_name for ss_field in fields]
    return [{key: value for key, value in row.items() if key in aux_list_cols} for row in data_list]


def _filter_model_query(query: SelectOfScalar, filter_model: Optional[Dict], model: Any
                        ) -> SelectOfScalar:
    """
    Add filters to select query according to filter model

    In case of a null filter model, simply return the initial query
    """
    try:
        for col_name in filter_model.keys():  # type: ignore
            query = _process_individual_filter(query, filter_model[col_name],
                                               col_name, model)  # type: ignore
        return query
    except AttributeError:
        return query


def _process_individual_filter(query: SelectOfScalar, filtering_elt: Dict, col_name: str,
                               model: Any) -> SelectOfScalar:
    """
    Add the filter associated to the selected column
    """
    implem_dict = {
        'text': _implement_text_filter,
        'number': _implement_number_filter,
        'set': _implement_set_filter,
    }
    return implem_dict[filtering_elt['filterType']](query, filtering_elt,
                                                    getattr(model, col_name))


def _implement_text_filter(query: SelectOfScalar, filtering_elt: Dict,
                           field: InstrumentedAttribute) -> SelectOfScalar:
    """
    Implementation of text filter in this setting

    NB: '_filter_str_ilike_field' requires an 'operator' which it does not use hence the '' below.
    """
    operator_dict = {
        'contains': ServerSideFilter.ILIKESTR,
        'startsWith': ServerSideFilter.STARTSTR,
        'equals': ServerSideFilter.STRICTSTR,
        'notContains': ServerSideFilter.NOT_CONTAINS_STR
    }
    return SERVER_SIDE_FILTERS[
        operator_dict[filtering_elt['type']]](field, query, '', filtering_elt.get('filter', ''))


def _implement_number_filter(query: SelectOfScalar, filtering_elt: Dict,
                             field: InstrumentedAttribute) -> SelectOfScalar:
    """
    Implementation of number filter in this setting

    NB: '_filter_str_ilike_field' requires an 'operator' which it does not use hence the '' below.
    """
    operator_dict = {
        'greaterThanOrEqual': '>=',
        'lessThanOrEqual': '<=',
        'notEqual': '!=',
        'equals': '=',
        'greaterThan': '>',
        'lessThan': '<',
    }

    return SERVER_SIDE_FILTERS[ServerSideFilter.NUM](field, query,
                                                     operator_dict[filtering_elt['type']],
                                                     filtering_elt.get('filter', ''))


def _implement_set_filter(query: SelectOfScalar, filtering_elt: Dict,
                          field: InstrumentedAttribute) -> SelectOfScalar:
    """
    Implementation of set filter in this setting
    """
    return query.where(col(field).in_(filtering_elt['values']))
