from collections.abc import Iterable, Generator
from itertools import islice
from typing import TypeVar

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
