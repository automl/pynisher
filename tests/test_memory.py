from pynisher import Pynisher
from pynisher.util import memconvert
from pynisher.exceptions import MemorylimitException

import pytest


def mb_as_bytes(x: float) -> int:
    return int(x * (2**20))


def usememory(x: float) -> None:
    nbytes = memconvert(x, "MB")
    bytearray(nbytes)
    return


@pytest.mark.parametrize("limit_mb", [1, 5, 100, 1000])
def test_fail(limit_mb: int) -> None:
    """Using more than the allocated memory should raise an Error"""
    restricted_func = Pynisher(usememory, memory=limit)

    with pytest.raises(MemorylimitException):
        restricted_func(limit * 2)


@pytest.mark.parametrize("limit_mb", [1000])
def test_success(limit_mb: int) -> None:
    """Using less than the allocated memory should be fine"""
    restricted_func = Pynisher(usememory, memory=limit)
    restricted_func(int(limit / 1000))
