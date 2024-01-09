"""
Simple Pydantic wrapper classes around BaseModel to accommodate for orm and frozen cases
"""
from pydantic import BaseModel


class Basic(BaseModel):
    """
    Basic pydantic configuration
    """

    class Config:
        """
        Allow mutation in inheriting classes
        """
        allow_mutation = True
        arbitrary_types_allowed = True


class Frozen(BaseModel):
    """
    Frozen pydantic configuration
    """

    class Config:
        """
        Forbid mutation in order to freeze the inheriting classes
        """
        allow_mutation = False


class CustomFrozen(Frozen):
    """
    Frozen pydantic configuration for custom types
    """
    class Config:
        """
        Allow arbitrary custom types
        """
        arbitrary_types_allowed = True


class OrmFrozen(CustomFrozen):
    """
    Frozen pydantic configuration for orm like object
    """

    class Config:
        """
        Allow to create object from orm one
        """
        orm_mode = True
