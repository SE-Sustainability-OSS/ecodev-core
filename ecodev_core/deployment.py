"""
Module implementing all types of deployment
"""
from enum import Enum
from enum import unique


@unique
class Deployment(str, Enum):
    """
    Enum listing all types of deployment
    """
    LOCAL = 'local'
    NON_PROD = 'nonprod'
    PREPROD = 'preprod'
    PROD = 'prod'
