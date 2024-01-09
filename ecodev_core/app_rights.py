"""
Module implementing the sqlmodel orm part of the right table
"""
from typing import Optional
from typing import TYPE_CHECKING

from sqlmodel import Field
from sqlmodel import Relationship
from sqlmodel import SQLModel


if TYPE_CHECKING:  # pragma: no cover
    from ecodev_core.app_user import AppUser


class AppRight(SQLModel, table=True):  # type: ignore
    """
    Simple right class: listing all app_services that a particular user can access to
    """
    __tablename__ = 'app_right'
    id: Optional[int] = Field(default=None, primary_key=True)
    app_service: str
    user_id: Optional[int] = Field(default=None, foreign_key='app_user.id')
    user: Optional['AppUser'] = Relationship(back_populates='rights')
