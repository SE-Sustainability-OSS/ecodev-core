"""
Module implementing all permission levels an application user can have
"""
from enum import Enum
from enum import unique


@unique
class Permission(str, Enum):
    """
    Enum listing all permission levels an application user can have
    """
    ADMIN = 'Admin'
    Consultant = 'Consultant'
    Client = 'Client'
