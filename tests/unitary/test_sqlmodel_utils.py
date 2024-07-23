"""
Module testing SQLModel helpers
"""
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field

from ecodev_core import SafeTestCase
from ecodev_core.sqlmodel_utils import SQLModelWithVal


class FooBase(SQLModelWithVal):
    """
    Example base class to illustrate the table validation behaviour of SQLModelWithVal
    """
    bar: int

    @field_validator('bar', mode='before')
    def convert_bar(cls, bar):
        """
        Example validation
        """
        return int(bar / 1_000_000)


class Foo(FooBase, table=True):  # type: ignore
    """
    Example class to illustrate the table validation behaviour of SQLModelWithVal
    """
    id: Optional[int] = Field(default=None, primary_key=True)


class SQLModelTest(SafeTestCase):
    """
    Class testing validation behaviour of SQLModelWithVal
    """

    def test_init_without_validation(self):
        """
        Test creation without validation
        """
        foo = Foo(bar=3_000_000)
        self.assertEqual(foo.bar, 3_000_000)

    def test_init_with_validation(self):
        """
        Test creation with validation
        """
        foo = Foo.create(bar=3_000_000)
        self.assertEqual(foo.bar, 3)
