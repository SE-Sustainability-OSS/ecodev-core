"""
Module implementing postgresql connection
"""
from typing import Callable
from typing import List
from typing import Optional
from urllib.parse import quote

from sqlalchemy import delete
from sqlalchemy import text
from sqlmodel import create_engine
from sqlmodel import Session
from sqlmodel import SQLModel

from ecodev_core.logger import logger_get
from ecodev_core.settings import SETTINGS

log = logger_get(__name__)


SETTINGS_DB = SETTINGS.database  # type: ignore[attr-defined]
_PASSWORD = quote(SETTINGS_DB.db_password, safe='')
_USER = SETTINGS_DB.db_username
_HOST = SETTINGS_DB.db_host
_PORT = SETTINGS_DB.db_port
_NAME = SETTINGS_DB.db_name
DB_URL = f'postgresql://{_USER}:{_PASSWORD}@{_HOST}:{_PORT}/{_NAME}'
default_test_db = 'test_db'
try:
    TEST_DB = SETTINGS_DB.db_test_name or default_test_db
except AttributeError:
    TEST_DB = default_test_db
TEST_DB_URL = f'postgresql://{_USER}:{_PASSWORD}@{_HOST}:{_PORT}/{TEST_DB}'
_ADMIN_DB_URL = f'postgresql://{_USER}:{_PASSWORD}@{_HOST}:{_PORT}/postgres'
engine = create_engine(DB_URL, pool_pre_ping=True)


def exec_admin_queries(queries: list[str]) -> None:
    """
    execute sequentially queries from the admin db
    """
    admin_engine = create_engine(_ADMIN_DB_URL, isolation_level='AUTOCOMMIT')
    with admin_engine.connect() as conn:
        for query in queries:
            conn.execute(text(query))
    admin_engine.dispose()


def create_db_and_tables(model: Callable, excluded_tables: Optional[List[str]] = None) -> None:
    """
    Create all tables based on the declared schemas in core/models thanks to sqlmodel
    Does not create the tables which are passed in the optional list of excluded tables,
    must be the table names
    """
    log.info(f'Inserting on the fly {model} and all other domain tables')
    SQLModel.metadata.tables = {table: meta_data for table, meta_data in
                                SQLModel.metadata.__dict__.get('tables').items()
                                if not excluded_tables or table
                                not in excluded_tables}
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
