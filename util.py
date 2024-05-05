import itertools
from collections.abc import Iterable, Generator, Callable
from itertools import islice
from typing import TypeVar

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


def vector_close_equals(v1, v2, /, *, threshold=0.001) -> bool:
    return all(abs(v1[i] - v2[i]) <= threshold for i in range(min(len(v1), len(v2))))


def matrix_close_equals(m1, m2, /, *, threshold=0.0001) -> bool:
    return all(
        vector_close_equals(m1[i], m2[2], threshold=threshold)
            for i in range(min(len(m1), len(m2)))
    )


def duplicates_by_predicate(
    values: dict[int, T] | Iterable[T],
    predicate: Callable[[T, T], bool]
) -> dict[int, int]:
    vals_dict: dict[int, T] = values if type(values) is dict else {i: v for i, v in enumerate(values)}
    duplicates: dict[int, int] = {}

    for (idx_1, val_1), (idx_2, val_2) in itertools.combinations(vals_dict.items(), 2):
        if idx_1 in duplicates:
            continue

        if predicate(val_1, val_2):
            duplicates[idx_2] = idx_1

    return duplicates


def strip_suffix(blender_name: str):
    if "." not in blender_name:
        return blender_name

    head, tail = blender_name.rsplit(".")
    if tail.isnumeric():
        return head
    return blender_name
