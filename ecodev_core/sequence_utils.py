"""
Module implementing helper methods working with sequences
"""

from typing import Generator
from typing import Sequence
from typing import TypeVar

T = TypeVar('T', bound=object)


def batch_iterable(to_batch: Sequence[T],
                   batch_size: int) -> Generator[tuple[int, Sequence[T]], None, None]:
    """
    Yields batches of size batch_size from the given sequence.
    """
    for i in range(0, len(to_batch), batch_size):
        yield i, to_batch[i:i+batch_size]
