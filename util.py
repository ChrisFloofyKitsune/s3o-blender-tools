from collections.abc import Iterable, Generator, Callable, Collection
from itertools import islice
from typing import TypeVar

from mathutils import Vector

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


def close_to_comparator(*, threshold=0.001) -> Callable[[Vector, Vector], bool]:
    return lambda v1, v2: all(abs(v1[i] - v2[i]) <= threshold for i in range(min(len(v1), len(v2))))


def duplicates_by_predicate(
    values: dict[int, T] | Collection[T],
    predicate: Callable[[T, T], bool]
) -> dict[int, int]:
    vals_dict: dict[int, T] = values if type(values) is dict else {i: v for i, v in enumerate(values)}
    duplicates: dict[int, int] = {}

    for idx_1, val_1 in vals_dict.items():
        if idx_1 in duplicates:
            continue

        for idx_2, val2 in vals_dict.items():
            if idx_1 == idx_2:
                continue

            if predicate(val_1, val2):
                duplicates[idx_2] = idx_1

    return duplicates
