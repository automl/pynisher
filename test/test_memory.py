import platform

from pynisher import MemoryLimitException, Pynisher, contexts, supports
from pynisher.util import Monitor, memconvert

import pytest

if not supports("memory"):
    pytest.skip(
        f"Doesn't support limiting memory on {platform.platform()} ",
        allow_module_level=True,
    )


def usememory(x: int) -> int:
    """Use a certain amount of memory in B"""
    bytearray(int(x))
    try:
        import resource

        print(resource.getrlimit(resource.RLIMIT_AS))
        print(resource.getrlimit(resource.RLIMIT_DATA))
    except Exception:
        pass

    return x


@pytest.mark.parametrize("limit", [1, 10, 100, 1000])
@pytest.mark.parametrize("context", contexts)
def test_fail(limit: int, context: str) -> None:
    """Using more than the allocated memory should raise an Error"""
    allocate = limit * 3

    restricted_func = Pynisher(usememory, memory=(limit, "MB"), context=context)

    with pytest.raises(MemoryLimitException):
        allocation_bytes = memconvert(allocate, frm="MB", to="B")
        restricted_func(allocation_bytes)


@pytest.mark.parametrize("limit", [1, 10, 100, 1000])
@pytest.mark.parametrize("context", contexts)
def test_success(limit: int, context: str) -> None:
    """Using less than the allocated memory should be fine

    Processes take up some amount of memory natively, e.g. 37MB was preallocated
    for my own run on Linx where "fork" is used.

    Hence, we skip if the test limit is not enough
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

    restricted_func = Pynisher(usememory, memory=(limit, "MB"), context=context)

    allocation_bytes = memconvert(allocate, frm="MB", to="B")
    restricted_func(allocation_bytes)
