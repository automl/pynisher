"""
Because limiting on windows sets limits on a Job, a thing that wraps
a process twice, in a manner quite different to Unix systems, we test
that using both limits do not interfere with
"""
from pynisher import (
    CpuTimeoutException,
    MemoryLimitException,
    Pynisher,
    contexts,
    supports,
)

import pytest

from test.util import cputime_sleep, usememory

if not supports("memory") or not supports("cpu_time"):
    pytest.skip("Tests specifically for cputime and memory", allow_module_level=True)


@pytest.mark.parametrize("context", contexts)
def test_cputime_limit(context: str) -> None:
    """
    Expects
    -------
    * With a cputime limit set and a memory limit set, spending too long computing
      should raise a cpu time limit
    """
    mem_limit = (100, "MB")
    cputime_limit = 2

    busy = 10

    with pytest.raises(CpuTimeoutException):
        with Pynisher(
            cputime_sleep,
            memory=mem_limit,
            cpu_time=cputime_limit,
            context=context,
        ) as rf:
            print(rf(busy))


@pytest.mark.parametrize("context", contexts)
def test_memory_limit(context: str) -> None:
    """
    Expects
    -------
    * With a cputime limit set and a memory limit set, allocating too much memory
      should still raise a MemoryLimitException
    """
    mem_limit = (100, "MB")
    cputime_limit = 100

    allocate_mem = (200, "MB")

    with pytest.raises(MemoryLimitException):
        with Pynisher(
            usememory,
            memory=mem_limit,
            cpu_time=cputime_limit,
            context=context,
        ) as rf:
            rf(allocate_mem)
