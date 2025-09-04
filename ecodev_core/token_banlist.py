"""
Module implementing the token ban list table
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field
from sqlmodel import SQLModel


class TokenBanlist(SQLModel, table=True):  # type: ignore
    """
    A token banlist: timestamped banned token.
    """
    __tablename__ = 'token_banlist'
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    token: str = Field(index=True)
