"""
Module testing sequence utils methods
"""
import unittest

from ecodev_core import batch_sequence


class SequenceUtilsTest(unittest.TestCase):
    """
    Class testing sequence utils methods
    """

    def test_batch_sequence_empty(self):
        """
        test batch_sequence with empty sequence yields no batches
        """
        batches = list(batch_sequence([], 3))
        self.assertEqual(batches, [])

    def test_batch_sequence_smaller_than_batch_size(self):
        """
        test batch_sequence when sequence is shorter than batch_size
        """
        batches = list(batch_sequence([1, 2], 3))
        self.assertEqual(batches, [(0, [1, 2])])

    def test_batch_sequence_exact_batch_size(self):
        """
        test batch_sequence when sequence length equals batch_size
        """
        batches = list(batch_sequence([1, 2, 3], 3))
        self.assertEqual(batches, [(0, [1, 2, 3])])

    def test_batch_sequence_one_full_one_partial(self):
        """
        test batch_sequence with one full batch and one partial batch
        """
        batches = list(batch_sequence([1, 2, 3, 4], 3))
        self.assertEqual(batches, [(0, [1, 2, 3]), (3, [4])])

    def test_batch_sequence_multiple_full_batches(self):
        """
        test batch_sequence with multiple full batches
        """
        batches = list(batch_sequence([1, 2, 3, 4, 5, 6], 2))
        self.assertEqual(
            batches,
            [(0, [1, 2]), (2, [3, 4]), (4, [5, 6])],
        )

    def test_batch_sequence_partial_last_batch(self):
        """
        test batch_sequence with partial last batch
        """
        batches = list(batch_sequence([1, 2, 3, 4, 5], 2))
        self.assertEqual(
            batches,
            [(0, [1, 2]), (2, [3, 4]), (4, [5])],
        )

    def test_batch_sequence_batch_size_one(self):
        """
        test batch_sequence with batch_size 1
        """
        batches = list(batch_sequence(['a', 'b', 'c'], 1))
        self.assertEqual(
            batches,
            [(0, ['a']), (1, ['b']), (2, ['c'])],
        )

    def test_batch_sequence_works_with_tuple(self):
        """
        test batch_sequence works with tuple (Sequence)
        """
        batches = list(batch_sequence((10, 20, 30), 2))
        self.assertEqual(batches, [(0, (10, 20)), (2, (30,))])
