"""
Module implementing the Version table
"""
from datetime import datetime
from enum import Enum
from enum import EnumType
from enum import unique
from typing import Optional

from sqlmodel import desc
from sqlmodel import Field
from sqlmodel import Index
from sqlmodel import select
from sqlmodel import Session
from sqlmodel import SQLModel


@unique
class ColType(str, Enum):
    """
    Enum listing all col types allowed to be stored in version
    """
    STR = 'str'
    BOOL = 'bool'
    INT = 'int'
    FLOAT = 'float'
    DATE = 'datetime'
    ENUM = 'enum'


COL_TYPES = str | int | bool | float | datetime | Enum | None


class Version(SQLModel, table=True):  # type: ignore
    """
    Table handling versioning.

    Attributes are:
        - table: the table to version
        - column: the column of table to version
        - row_id: the row id of the column of table to version
        - col_type: the column type
        - value: the value to store (previous row/column/table version)
    """
    __tablename__ = 'version'
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    table: str = Field(index=True)
    column: str = Field(index=True)
    row_id: int = Field(index=True)
    col_type: ColType
    value: str | None = Field(index=True)

    __table_args__ = (
        Index(
            'version_filter_id',
            'table',
            'row_id',
            'column'
        ),
    )

    @classmethod
    def from_table_row(cls, table: str,
                       column: str,
                       row_id: int,
                       raw_type: type | EnumType,
                       raw_val: COL_TYPES
                       ) -> 'Version':
        """
        Create a new Version out of the passed information
        """
        col_type = _col_type_to_db(raw_type)
        value = _value_to_db(raw_val, col_type)
        return cls(table=table, column=column, row_id=row_id, col_type=col_type, value=value)


def get_versions(table: str, column: str, row_id: int, session: Session) -> list[Version]:
    """
    Retrieve all previous versions of a (table, column, row_id) triplet
    """
    query = select(Version).where(Version.table == table, Version.row_id == row_id,
                                  Version.column == column).order_by(desc(Version.created_at))
    return session.exec(query).all()


def get_row_versions(table: str, row_id: int, session: Session) -> list[Version]:
    """
    Retrieve all previous versions of a (table, row_id) couples. Hence all columns previous versions
    """
    query = select(Version).where(Version.table == table, Version.row_id == row_id
                                  ).order_by(desc(Version.created_at))
    return session.exec(query).all()


def _col_type_to_db(col_type: type | EnumType) -> ColType:
    """
    Forge ColType out of passed col_type
    """
    if issubclass(int, col_type):
        return ColType.INT
    if issubclass(bool, col_type):
        return ColType.BOOL
    if issubclass(float, col_type):
        return ColType.FLOAT
    if issubclass(str, col_type):
        return ColType.STR
    if issubclass(datetime, col_type):
        return ColType.DATE
    return ColType.ENUM


def _value_to_db(value: COL_TYPES, col_type: ColType) -> str | None:
    """
    Convert a value to version to it's str version
    """
    if value is None:
        return None

    match col_type:
        case ColType.BOOL | ColType.STR | ColType.INT | ColType.FLOAT:
            return str(value)
        case ColType.DATE:
            return value.strftime('%Y-%m-%d %H:%M:%S.%f')  # type: ignore[union-attr]
        case ColType.ENUM:
            return value.name  # type: ignore[union-attr]
        case _:
            return None


def db_to_value(db_value: str | None, col_type: type | EnumType) -> COL_TYPES:
    """
    Convert back a str version value stored to a real value (types handled listed in ColType)
    NB: assumption that if the type is not known, this is an enum type.
    """
    if db_value is None:
        return None
    if col_type in [int, str, float]:
        return col_type(db_value)
    if col_type == bool:
        return db_value == 'True'
    if col_type == datetime:
        return datetime.strptime(db_value, '%Y-%m-%d %H:%M:%S.%f')
    return col_type[db_value]  # type: ignore[index]
