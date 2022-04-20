import sys

from pynisher import Pynisher
from pynisher.util import memconvert, Monitor
from pynisher.exceptions import MemorylimitException

import pytest


def usememory(x: int) -> None:
    """Use a certain amount of memory in MB"""
    print(Monitor().memory("MB"))
    bytearray(int(x))
    return


@pytest.mark.skipif(sys.platform == "darwin", reason="Can't limit memory on Darwin")
@pytest.mark.parametrize("limit", [1, 10, 100, 1000])
def test_fail(limit: int) -> None:
    """Using more than the allocated memory should raise an Error"""
    allocate = limit * 3

    restricted_func = Pynisher(usememory, memory=(limit, "MB"))

    with pytest.raises(MemorylimitException):
        allocation_bytes = memconvert(allocate, frm="MB", to="B")
        restricted_func(allocation_bytes)


@pytest.mark.skipif(sys.platform == "darwin", reason="Can't limit memory on Darwin")
@pytest.mark.parametrize("limit", [1, 10, 100, 1000])
def test_success(limit: int) -> None:
    """Using less than the allocated memory should be fine

    Processes take up some amount of memory natively, e.g. 37MB was preallocated
    for my own run. Hence, we skip if the test limit is not enough
    """
    allocate = limit / 3

    current_usage = Monitor().memory("MB")
    expected_usage = current_usage + allocate

    if expected_usage > limit:
        msg = (
            f"Limit {limit}MB is too low as the current usage is {current_usage}MB"
            f" with another {allocate}MB being allocated. This will total "
            f" {expected_usage}MB, over the limit."
        )
        pytest.skip(msg)

    restricted_func = Pynisher(usememory, memory=(limit, "MB"))

    allocation_bytes = memconvert(allocate, frm="MB", to="B")
    restricted_func(allocation_bytes)


if __name__ == "__main__":

    def f(x):
        """Allocates memory"""
        print("limit (MB) = ", Monitor().memlimit(units="MB"))
        print("usage before (MB) = ", Monitor().memory(units="MB"))
        print("Allocating (MB) = ", memconvert(x, to="MB"))
        z = bytearray(int(x))
        print("usage after (MB) = ", Monitor().memory(units="MB"))

    limit = 1000
    with Pynisher(f, memory=(limit, "MB")) as rf:
        allocate = limit / 2
        allocation_bytes = memconvert(allocate, frm="MB", to="B")
        rf(allocation_bytes)
