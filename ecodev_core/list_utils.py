"""
Module implementing helper methods working on lists
"""
from collections import defaultdict
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Optional
from typing import Union


def group_by_value(list_to_group: List[Any]) -> Dict[Any, List[int]]:
    """
    Given a list, group together all equal values by storing them in a dictionary.
    The keys are the unique list values (think about overriding the class equals if you pass
    to this method your custom classes) and the values are list of ints, corresponding to the
    position of the current key in the original list.

    See https://towardsdatascience.com/explaining-the-settingwithcopywarning-in-pandas-ebc19d799d25
    for why not to use df['base_year'][values] for instance
    """

    indices: Dict[Any, List[int]] = defaultdict(list)
    for i in range(len(list_to_group)):
        indices[list_to_group[i]].append(i)
    return indices


def first_or_default(sequence: Union[List[Any], None],
                     condition: Union[Callable, None] = None,
                     default: Optional[Any] = None
                     ) -> Union[Any, None]:
    """
    Returns the first element of a sequence, or default value if the sequence contains no elements.
    """
    if not sequence:
        return default

    if condition is None:
        return next(iter(sequence), default)
    return next((elt for elt in sequence if condition(elt)), default)


def lselect(sequence: List[Any], condition: Union[Callable, None] = None) -> List[Any]:
    """
    Filter the passed sequence according to the passed condition
    """
    return list(filter(condition, sequence))


def lselectfirst(sequence: List[Any], condition: Union[Callable, None] = None) -> Union[Any, None]:
    """
    Select the filtered element of the passed sequence according to the passed condition
    """

    return filtered_list[0] if (filtered_list := list(filter(condition, sequence))) else None


def first_transformed_or_default(sequence: List[Any], transformation: Callable) -> Union[Any, None]:
    """
    Returns the first non-trivial transformed element of a sequence,
     or default value if no non-trivial transformed elements are found.
    """
    return next((fx for elt in sequence if (fx := transformation(elt)) is not None), None)
