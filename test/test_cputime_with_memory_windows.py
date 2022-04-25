"""
Because limiting on windows sets limits on a Job, a thing that wraps
a process twice, in a manner quite different to Unix systems, we test
that using both limits does not interfere with
"""
import sys
import time

from pynisher import CpuTimeoutException, MemoryLimitException, Pynisher
from pynisher.util import memconvert

import pytest

if not sys.platform.lower().startswith("win"):
    pytest.skip("Tests specifically for windows", allow_module_level=True)


def usememory(x: int) -> None:
    """Use a certain amount of memory in B"""
    bytearray(int(x))
    return


def cpu_busy(execution_time: int) -> float:
    """Keeps the cpu busy for `execution_time` wall clock seconds

    Parameters
    ----------
    execution_time: int
        Amount of seconds to keep the cpu busy for
    """
    start = time.perf_counter()
    while True:
        duration = time.perf_counter() - start
        if duration > execution_time:
            break

    return duration


def test_cputime_limit() -> None:
    """
    Expects
    -------
    * With a cputime limit set and a memory limit set, spending too long computing
      should raise a cpu time limit
    """
    mem_limit = (100, "MB")
    cputime_limit = 2

    walltime_busy = 10

    with pytest.raises(CpuTimeoutException):
        with Pynisher(cpu_busy, memory=mem_limit, cpu_time=cputime_limit) as rf:
            rf(walltime_busy)


def test_memory_limit() -> None:
    """
    Expects
    -------
    * With a cputime limit set and a memory limit set, allocating too much memory
      should still raise a MemoryLimitException
    """
    mem_limit = (100, "MB")
    cputime_limit = 100

    allocate_mem = memconvert(200, to="MB")

    with pytest.raises(MemoryLimitException):
        with Pynisher(usememory, memory=mem_limit, cpu_time=cputime_limit) as rf:
            rf(allocate_mem)
