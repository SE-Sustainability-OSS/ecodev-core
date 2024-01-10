"""
Simple Pydantic wrapper classes around BaseModel to accommodate for orm and frozen cases
"""
from pydantic import BaseModel
from pydantic import ConfigDict


class Basic(BaseModel):
    """
    Basic pydantic configuration
    """
    model_config = ConfigDict(frozen=False, arbitrary_types_allowed=True)


class Frozen(BaseModel):
    """
    Frozen pydantic configuration
    """
    model_config = ConfigDict(frozen=True)


class CustomFrozen(Frozen):
    """
    Frozen pydantic configuration for custom types
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)


class OrmFrozen(CustomFrozen):
    """
    Frozen pydantic configuration for orm like object
    """
    model_config = ConfigDict(from_attributes=True)
