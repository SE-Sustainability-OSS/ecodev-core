"""
Module handling CRUD and version operations
"""
from functools import partial
from typing import Union

import pandas as pd
import progressbar
from sqlmodel import and_
from sqlmodel import Field
from sqlmodel import inspect
from sqlmodel import select
from sqlmodel import Session
from sqlmodel import SQLModel
from sqlmodel import update
from sqlmodel.main import SQLModelMetaclass
from sqlmodel.sql.expression import SelectOfScalar

from ecodev_core.version import get_row_versions
from ecodev_core.version import Version

BATCH_SIZE = 5000
FILTER_ON = 'filter_on'
INFO = 'info'


def sfield(**kwargs):
    """
    Field constructor for columns not to be versioned. Those are the columns on which to select.
    They morally are a sort of unique identifier of a row (like id but more business meaningful)
    """
    return Field(**kwargs, sa_column_kwargs={INFO: {FILTER_ON: True}})


def field(**kwargs):
    """
    Field constructor for columns to be versioned.
    """
    return Field(**kwargs, sa_column_kwargs={INFO: {FILTER_ON: False}})


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

    for col, val in {k: v for k, v in db.items() if k in to_update and v != to_update[k]}.items():
        session.add(Version.from_table_row(table, col, row_id, col_types[col], val))

    return update(db_schema).where(db_schema.id == row_id).values(**to_update)


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


def upsert_data(df: Union[pd.DataFrame], db_schema: SQLModelMetaclass, session: Session) -> None:
    """
    Upsert the passed df into db_schema db.
    """
    upsert_dict_data([x.to_dict() for _, x in df.iterrows()], db_schema, session)


def upsert_dict_data(data: list[dict], db_schema: SQLModelMetaclass, session: Session) -> None:
    """
    Upsert the passed list of dicts (corresponding to db_schema) into db_schema db.
    """
    selector = partial(upsert_selector, db_schema=db_schema)
    updator = partial(upsert_updator, db_schema=db_schema)
    batches = [data[i:i + BATCH_SIZE] for i in range(0, len(data), BATCH_SIZE)]

    for batch in progressbar.progressbar(batches, redirect_stdout=False):
        for row in batch:
            new_object = db_schema(**row)
            if in_db := session.exec(selector(new_object)).first():
                session.exec(updator(new_object, in_db.id, session))
            else:
                session.add(new_object)
        session.commit()
