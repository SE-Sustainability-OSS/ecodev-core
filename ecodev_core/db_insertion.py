"""
Module implementing functions to insert data within the db
"""
from io import BytesIO
from pathlib import Path
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Union

import pandas as pd
from fastapi import BackgroundTasks
from fastapi import UploadFile
from pandas import ExcelFile
from sqlmodel import Session
from sqlmodel import SQLModel
from sqlmodel.sql.expression import SelectOfScalar

from ecodev_core.logger import log_critical
from ecodev_core.logger import logger_get
from ecodev_core.pydantic_utils import CustomFrozen
from ecodev_core.safe_utils import SimpleReturn


log = logger_get(__name__)


class Insertor(CustomFrozen):
    """
    Configuration class to insert date into the postgresql sb.

    Attributes are:

        - reductor: how to create or update a row in db
        - db_schema: the default constructor of the sqlmodel based class defining the db table
        - selector: the criteria on which to decide whether to create or update (example: only add
          a user if a user with the same name is not already present in the db)
        - convertor: how to convert the raw csv/excel passed by the user to json like db rows
        - read_excel_file: whether to insert data based on an xlsx (if true) or a csv (if false)
    """
    reductor: Callable[[Any, Any], Any]
    db_schema: Callable
    selector: Callable[[Any], SelectOfScalar]
    convertor: Callable[[Union[pd.DataFrame, ExcelFile]], List[Dict]]
    read_excel_file: bool = True


def generic_insertion(df_or_xl: Union[pd.DataFrame, ExcelFile, Path],
                      session: Session,
                      insertor: Callable[[Union[pd.DataFrame, pd.ExcelFile], Session], None],
                      background_tasks: Union[BackgroundTasks, None] = None):
    """
    Generic insertion of temperature tool related csv into db
    """
    try:
        if background_tasks:
            background_tasks.add_task(insertor, df_or_xl, session)
        else:
            insertor(df_or_xl, session)
        return SimpleReturn.route_success()
    except Exception as error:
        log_critical(f'Something wrong happened: {error}', log)
        return SimpleReturn.route_failure(str(error))


async def insert_file(file: UploadFile, insertor: Insertor, session: Session) -> None:
    """
    Inserts an uploaded file into a database
    """
    df_raw = await get_raw_df(file, insertor.read_excel_file)
    insert_data(df_raw, insertor, session)


def insert_data(df:  Union[pd.DataFrame, ExcelFile], insertor: Insertor, session: Session) -> None:
    """
    Inserts a csv/df into a database
    """
    for row in insertor.convertor(df):
        session.add(create_or_update(session, row, insertor))
    session.commit()


def create_or_update(session: Session, row: Dict, insertor: Insertor) -> SQLModel:
    """
    Create a new row in db if the selector insertor does not find existing row in db. Update the row
    otherwise.
    """
    db_row = insertor.db_schema(**row)
    if in_db_row := session.exec(insertor.selector(db_row)).first():
        return insertor.reductor(in_db_row, db_row)
    return db_row


async def get_raw_df(file: UploadFile,
                     read_excel_file: bool,
                     sep: str = ',') -> Union[pd.DataFrame, ExcelFile]:
    """
    Retrieves the raw data from the uploaded file at pandas format
    """
    contents = await file.read()
    if read_excel_file:
        return pd.ExcelFile(contents)

    buffer = BytesIO(contents)
    raw_content = pd.read_csv(buffer, sep=sep)
    buffer.close()
    return raw_content
