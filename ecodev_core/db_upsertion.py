"""
Module handling CRUD and version operations
"""
import enum
import json
import types
from datetime import datetime
from enum import EnumType
from functools import partial
from typing import Any
from typing import get_args
from typing import get_origin
from typing import Iterator
from typing import Union

import pandas as pd
import progressbar
from pydantic_core._pydantic_core import PydanticUndefined
from sqlmodel import and_
from sqlmodel import Field
from sqlmodel import inspect
from sqlmodel import select
from sqlmodel import Session
from sqlmodel import SQLModel
from sqlmodel import text
from sqlmodel import update
from sqlmodel.main import SQLModelMetaclass
from sqlmodel.sql.expression import SelectOfScalar

from ecodev_core.version import get_row_versions
from ecodev_core.version import Version

BATCH_SIZE = 5000
FILTER_ON = 'filter_on'
INFO = 'info'
SA_COLUMN_KWARGS = 'sa_column_kwargs'


def add_missing_enum_values(enum: EnumType, session: Session, new_vals: list | None = None) -> None:
    """
    Add to an existing enum its missing db values. Do so by retrieving what is already in db, and
    insert what is new.

    NB: new_val argument is there for testing purposes
    """

    for val in [e.name for e in new_vals or enum if e.name not in get_enum_values(enum, session)]:
        session.execute(text(f"ALTER TYPE {enum.__name__.lower()} ADD VALUE IF NOT EXISTS '{val}'"))
        session.commit()


def get_enum_values(enum: EnumType, session: Session) -> set[str]:
    """
    Return all enum values in db for the passed enum.
    """
    result = session.execute(text(
        """
        SELECT enumlabel FROM pg_enum
        JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
        WHERE pg_type.typname = :enum_name
        """
    ), {'enum_name': enum.__name__.lower()})
    return {x[0] for x in result}


def sfield(**kwargs):
    """
    Field constructor for columns not to be versioned. Those are the columns on which to select.
    They morally are a sort of unique identifier of a row (like id but more business meaningful)
    """
    sa_column_kwargs = _get_sa_column_kwargs(kwargs, sfield=True)
    return Field(**kwargs, sa_column_kwargs=sa_column_kwargs)


def field(**kwargs):
    """
    Field constructor for columns to be versioned.
    """
    sa_column_kwargs = _get_sa_column_kwargs(kwargs, sfield=False)
    return Field(**kwargs, sa_column_kwargs=sa_column_kwargs)


def _get_sa_column_kwargs(kwargs, sfield: bool) -> dict:
    """
    Combine existing sa_column_kwargs with the new field necessary for versioning
    """
    if not (additional_vals := kwargs.get(SA_COLUMN_KWARGS)):
        return {INFO: {FILTER_ON: sfield}}
    kwargs.pop(SA_COLUMN_KWARGS)
    return additional_vals | {INFO: {FILTER_ON: sfield}}


def upsert_selector(values: SQLModel, db_schema: SQLModelMetaclass) -> SelectOfScalar:
    """
    Return the query allowing to select on column not to be versioned values.
    """
    conditions = [getattr(db_schema, x.name) == getattr(values, x.name)
                  for x in inspect(db_schema).c if x.info.get(FILTER_ON) is True]
    return select(db_schema).where(and_(*conditions))


def upsert_updator(values: SQLModel,
                   row_id: int,
                   session: Session,
                   db_schema: SQLModelMetaclass
                   ) -> None:
    """
    Update the passed row_id from db_schema db with passed new_values.
     Only update columns to be versioned.

    At the same time, store previous (column, row_id) versions for all columns that changed values.
    """
    to_update = {col.name: getattr(values, col.name)
                 for col in inspect(db_schema).c if col.info.get(FILTER_ON) is False}
    db = session.exec(select(db_schema).where(db_schema.id == row_id)).first().model_dump()
    col_types = {x: y.annotation for x, y in db_schema.__fields__.items()}
    table = db_schema.__tablename__

    for col, val in {k: v for k, v in db.items() if k in to_update and _value_comparator(
            v, to_update[k])}.items():
        session.add(Version.from_table_row(table, col, row_id, col_types[col], val))

    return update(db_schema).where(db_schema.id == row_id).values(**to_update)


def _value_comparator(v: Any, to_update: Any) -> bool:
    """
    Performs a comparison between the value in db and the value to be upserted
    """
    return v.date() != to_update.date() if isinstance(v, datetime) else v != to_update


def upsert_deletor(values: SQLModel, session: Session):
    """
    Delete row in db corresponding to the passed values, selecting on columns not to be versioned.
    """
    db_schema = values.__class__
    if in_db := session.exec(upsert_selector(values, db_schema=db_schema)).first():
        for version in get_row_versions(db_schema.__tablename__, in_db.id, session):
            session.delete(version)
        session.delete(in_db)
        session.commit()


def upsert_df_data(df: Union[pd.DataFrame], db_schema: SQLModelMetaclass, session: Session) -> None:
    """
    Upsert the passed df into db_schema db.
    """
    upsert_data([x.to_dict() for _, x in df.iterrows()], session, raw_db_schema=db_schema)


def upsert_data(data: list[dict | SQLModelMetaclass],
                session: Session,
                raw_db_schema: SQLModelMetaclass | None = None) -> None:
    """
    Upsert the passed list of dicts (corresponding to db_schema) into db_schema db.
    """
    db_schema = raw_db_schema or data[0].__class__
    selector = partial(upsert_selector, db_schema=db_schema)
    updator = partial(upsert_updator, db_schema=db_schema)
    batches = [data[i:i + BATCH_SIZE] for i in range(0, len(data), BATCH_SIZE)]

    for batch in progressbar.progressbar(batches, redirect_stdout=False):
        for row in batch:
            new_object = db_schema(**row) if isinstance(row, dict) else row
            if in_db := session.exec(selector(new_object)).first():
                session.exec(updator(new_object, in_db.id, session))
            else:
                session.add(new_object)
        session.commit()


def get_sfield_columns(db_model: SQLModelMetaclass) -> list[str]:
    """
    get all the columsn flagged as sfields from schema
    Args:
        db_model (SQLModelMetaclass): db_model
    Returns:
        list of str with the names of the columns
    """
    return [
        x.name
        for x in inspect(db_model).c
        if x.info.get(FILTER_ON) is True
    ]


def filter_to_sfield_dict(row: dict | SQLModelMetaclass,
                          db_schema: SQLModelMetaclass | None = None) \
        -> dict[str, dict | SQLModelMetaclass]:
    """
    Returns a dict with only sfields from object
    Args:
        row: any object with ecodev_core field and sfield
        db_schema (SQLModelMetaclass): db_schema. Use the schema of row if not specified
    Returns:
        dict
    """
    return {pk: getattr(row, pk)
            for pk in get_sfield_columns(db_schema or row.__class__)}


def add_missing_columns(model: Any, session: Session) -> None:
    """
      Create all columns corresponding to fields in the passed model that are not yet columns in the
     corresponding db table.

    NB: The ORM not permitting to create new columns, we unfortunately have to rely on sqlalchemy
     text sql statements.

    NB2: As of 2025/10/01, handle the creation of int, float, str, bool, bytes, JSONB, Enum columns

    NB3: possible to index columns, and to add foreign key.

    NB4: Possible to have a non NULL default value
    """
    table = model.__tablename__
    current_cols,  = get_existing_columns(table, session),
    for col, py_type, fld in [(c, p, f) for c, p, f in _get_cols(model) if c not in current_cols]:
        is_null = _is_type_nullable(py_type)
        default = _get_default_value(fld, is_null)
        _add_column(table, col, _py_type_to_sql(_clean_py_type(py_type)), default, is_null, session)
        if getattr(fld, 'index', False):
            _add_index(table, col, session)
        if isinstance((fk := getattr(fld, 'foreign_key', None)), str) and fk.strip():
            _add_foreign_key(f"{fk.split('.')[0]}(id)", table, col, session)
        session.commit()


def _get_default_value(fld: Any, nullable: bool) -> Any:
    """
    Find if any the field default value
    """
    if not nullable and hasattr(fld, 'default') and fld.default is not None:
        return fld.default
    return None


def _add_column(table: str,
                col: str,
                sql_type: str,
                default: Any,
                nullable: bool,
                session: Session
                ) -> None:
    """
     Add the new column with sql_type to the passed table
    """
    session.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {sql_type} '
                         f'{_get_additional_request(col, sql_type, default, nullable)}'))


def _get_additional_request(col: str, sql_type: str, default_value: Any, nullable: bool) -> str:
    """
    Add if any the default value for the passed col.
    """
    if nullable:
        return 'NULL'

    if default_value is not None:
        if (default_sql := _python_default_to_sql(default_value, sql_type)) == 'NULL':
            raise ValueError(f'Non-nullable column {col} requires a default_value')
        return f'DEFAULT {default_sql} NOT NULL'

    raise ValueError(f'Non-nullable column {col} requires a default_value')


def _add_index(table: str, col: str, session: Session):
    """
    Index the new table column
    """
    session.execute(text(f'CREATE INDEX IF NOT EXISTS ix_{table}_{col} ON {table} ({col})'))


def _add_foreign_key(fk: str, table: str, col: str, session: Session):
    """
    Add a fk foreign key on the passed table column
    """
    session.execute(text(
        f'ALTER TABLE {table} ADD CONSTRAINT fk_{table}_{col} FOREIGN KEY ({col}) REFERENCES {fk}'))


def _get_cols(model: Any) -> Iterator[tuple[str, Any, Any]]:
    """
    Retrieve all fields and their corresponding sql types from the passed model
    """
    for col, field in model.model_fields.items():
        if (col_type := getattr(field, 'annotation', None)) is not None:
            yield col, col_type, field


def get_existing_columns(table_name: str, session: Session) -> set[str]:
    """
    Retrieve all column names from the passed table
    """
    result = session.execute(text('SELECT column_name FROM information_schema.columns WHERE '
                                  'table_name = :table_name'), {'table_name': table_name})
    return {r[0] for r in result}


def _clean_py_type(col_type: Any) -> Any:
    """
    Convert union and optional types to their non-None types, return directly passed type otherwise.
    - Handle Python 3.10+ UnionType (aka X | Y)
    - Unpack Optional types (Union[X, NoneType])
    """
    if isinstance(col_type, types.UnionType):
        if len((args := [t for t in col_type.__args__ if t is not type(None)])) == 1:
            return args[0]

    if get_origin(col_type) is Union:
        if len((args := [t for t in get_args(col_type) if t is not type(None)])) == 1:
            return args[0]

    return col_type


def _is_type_nullable(col_type: Any) -> bool:
    """
    Return True if col_type is Optional or Union[..., None].
    """
    if isinstance(col_type, types.UnionType):
        return type(None) in col_type.__args__

    if get_origin(col_type) is Union:
        return type(None) in get_args(col_type)

    return col_type is type(None)


def _python_default_to_sql(value: Any, sql_type: str) -> str:
    """
    Convert Python default to SQL literal, handling common types.
    """
    if value is None or value == PydanticUndefined:
        return 'NULL'
    if sql_type in ('VARCHAR', 'TEXT', 'CHAR'):
        safe_value = value.replace("'", "''")
        return f"'{safe_value}'"
    if sql_type in ('INTEGER', 'FLOAT', 'NUMERIC', 'DOUBLE PRECISION'):
        return str(value)
    if sql_type == 'BOOLEAN':
        return 'TRUE' if value else 'FALSE'
    if sql_type == 'BYTEA':
        if isinstance(value, bytes):
            return f"decode('{value.hex()}', 'hex')"
        raise ValueError('Default for BYTEA must be bytes')
    if sql_type == 'JSONB':
        json_str = json.dumps(value).replace("'", "''")
        return f"'{json_str}'::jsonb"
    if isinstance(value, enum.Enum):
        return f"'{str(value.name)}'"
    return str(value)


def _py_type_to_sql(col_type: type) -> str:
    """
    Convert a python type to a sql one. Only working for (as of 2025/10/01):
    - int
    - float
    - str
    - bool
    - bytes
    - jsonB
    - Enum
    NB: for enum, assumes type is already created in DB
    """
    if col_type is str:
        return 'VARCHAR'
    if col_type is int:
        return 'INTEGER'
    if col_type is float:
        return 'FLOAT'
    if col_type is bool:
        return 'BOOLEAN'
    if col_type is bytes:
        return 'BYTEA'
    if col_type is dict:
        return 'JSONB'
    if hasattr(col_type, '__members__'):
        return col_type.__name__.lower()
    raise ValueError(f'Unsupported column type: {col_type}')
