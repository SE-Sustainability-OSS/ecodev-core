"""
Module implementing postgresql connection
"""
from typing import Callable

from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict
from sqlalchemy import delete
from sqlmodel import create_engine
from sqlmodel import Session
from sqlmodel import SQLModel

from ecodev_core.logger import logger_get

log = logger_get(__name__)


class DbSettings(BaseSettings):
    """
    Settings class used to connect to the postgresql database
    """
    db_host: str
    db_port: str
    db_name: str
    db_username: str
    db_password: str
    model_config = SettingsConfigDict(env_file='.env')


DB = DbSettings()
DB_URL = f'postgresql://{DB.db_username}:{DB.db_password}@{DB.db_host}:{DB.db_port}/{DB.db_name}'
engine = create_engine(DB_URL)


def create_db_and_tables(model: Callable) -> None:
    """
    Create all tables based on the declared schemas in core/models thanks to sqlmodel
    """
    log.info(f'Inserting on the fly {model} and all other domain tables')
    SQLModel.metadata.create_all(engine)


def delete_table(model: Callable) -> None:
    """
    Delete all rows of the passed model from db
    """
    with Session(engine) as session:
        result = session.execute(delete(model))
        session.commit()
        log.info(f'Deleted {result.rowcount} rows')


def get_session():
    """
    Retrieves the session, used in Depends() attributes of fastapi routes
    """
    with Session(engine) as session:
        yield session


def info_message(model: Callable):
    """
    Create all tables based on the declared schemas in core/models thanks to sqlmodel
    """
    log.info(f'hack to get all models imported in an alembic env.py. {model}')
