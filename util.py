from collections.abc import Iterable, Generator
from itertools import islice
from typing import TypeVar

import numpy as np
import numpy.typing as npt

from mathutils import Matrix

TO_FROM_BLENDER_SPACE = Matrix(
    (
        (-1, 0, 0, 0),
        (0, 0, 1, 0),
        (0, 1, 0, 0),
        (0, 0, 0, 1),
    )
).freeze()
""" Ends up being just a couple of rotations. Also is it's own inverse! """

T = TypeVar('T')


def batched(iterable: Iterable[T], n) -> Generator[tuple[T]]:
    """
    Batch data into tuples of length n. The last batch may be shorter.
    batched('ABCDEFG', 3) --> ABC DEF G

    https://docs.python.org/3.11/library/itertools.html#itertools-recipes
    """

    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch


def extract_null_terminated_string(data: bytes, offset: int) -> str:
    """
    :param data: raw bytes
    :param offset: offset into bytes
    :return: bytes up to (not including) '\0' decoded as utf8 string
    """
    if offset == 0:
        return b"".decode()
    else:
        return data[offset:data.index(b'\x00', offset)].decode()


def make_duplicates_mapping(
    values: dict[int, npt.ArrayLike] | npt.ArrayLike,
    tolerance=0.001,
) -> dict[int, int]:
    np_array: npt.NDArray
    try:
        if type(values) is dict:
            if len(values) == 0:
                return dict()
            example_array = np.array(next(iter(values.values()), ()))
            np_array = np.full_like(example_array, fill_value=np.nan, shape=(max(values.keys())+1, *example_array.shape))
            np_array[np.array(list(values.keys()), dtype=int)] = [np.array(v) for v in values.values()]
        else:
            np_array = np.array(values)
            if np_array.size == 0:
                return {}

        indexes_of_originals = np.arange(len(np_array), dtype=int)

        for idx in range(len(np_array) - 1):
            current_value = np_array[idx]

            # skip if value is "empty" or if this value was already marked as a duplicate
            if np.all(np.isnan(current_value)):
                continue
            if indexes_of_originals[idx] < idx:
                continue

            slice_compare_results = np.isclose(np_array[idx + 1:], current_value, atol=tolerance)
            slice_compare_results = np.logical_and.reduce(slice_compare_results, (*range(0, np_array.ndim),)[1:])
            np.copyto(indexes_of_originals[idx + 1:], idx, where=slice_compare_results)
        result = {idx: orig_idx for idx, orig_idx in enumerate(indexes_of_originals) if idx != orig_idx}
        return result

    except Exception as err:
        print("WARNING could not find dupes!", err)
    return {}


def strip_suffix(blender_name: str):
    if "." not in blender_name:
        return blender_name

    head, tail = blender_name.rsplit(".")
    if tail.isnumeric():
        return head
    return blender_name
