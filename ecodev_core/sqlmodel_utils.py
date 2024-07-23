"""
module implementing SQLModel related helper methods. Related to validation
"""
from sqlmodel import SQLModel


class SQLModelWithVal(SQLModel):
    """
    Helper class to ease validation in SQLModel classes with table=True
    """
    @classmethod
    def create(cls, **kwargs):
        """
        Forces validation to take place, even for SQLModel classes with table=True
        """
        return cls(**cls.__bases__[0](**kwargs).model_dump())
