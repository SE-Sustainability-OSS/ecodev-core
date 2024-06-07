"""
Module implementing helper methods working on lists
"""
from collections import defaultdict
from itertools import groupby
from typing import Any
from typing import Callable
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple
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


def sort_by_keys(unsorted_dict: dict, reverse: bool = False) -> dict:
    """
    Returns a sorted dictionary out of the passed unsorted_dict.
    Sorting is done on unsorted_dict keys.
    If reverse is True, reverse sorting
    """
    return dict(sorted(unsorted_dict.items(), reverse=reverse))


def sort_by_values(unsorted_dict: dict, reverse: bool = False) -> dict:
    """
    Returns a sorted dictionary out of the passed unsorted_dict.
    Sorting is done on unsorted_dict values.
    If reverse is True, reverse sorting
    """
    return dict(sorted(unsorted_dict.items(), key=lambda item: item[1], reverse=reverse))


def first_func_or_default(sequence: list[Callable] | None,
                          elt: Any,
                          condition: Callable | None = None,
                          default: Any | None = None
                          ) -> Any | None:
    """
    Returns the first element of a functional sequence if a certain criteria is met
    or default value if the criteria is never met.
    The criteria is like so:
    - If no condition is provided, then
      just check that func applied on elt is not None
    - If a condition is provided, then
       check that condition applied on func(elt) is not None
    """
    if not sequence:
        return default

    return next((func(elt) for func in sequence if (condition or (lambda x: x))(func(elt))),
                default)


def group_by(sequence: List[Any], key: Union[Callable, None]) -> Iterator[Tuple[Any, List[Any]]]:
    """
    Extension of itertools groupby method.

    Reasons of existence:
        - do the sorting before the grouping to avoid the usual mistake of forgetting the sorting
        - convert the group Iterator to a list. More convenient that the default groupby behaviour
           in all cases where you need to iterate more than once on the group
    """
    for key, group in groupby(sorted(sequence, key=key), key=key):
        yield key, list(group)


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
