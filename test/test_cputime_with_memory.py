"""
Because limiting on windows sets limits on a Job, a thing that wraps
a process twice, in a manner quite different to Unix systems, we test
that using both limits does not interfere with
"""
import time

from pynisher import CpuTimeoutException, MemoryLimitException, Pynisher, supports
from pynisher.util import memconvert

import pytest

if not supports("memory") or not supports("cpu_time"):
    pytest.skip("Tests specifically for cputime and memory", allow_module_level=True)


def usememory(x: int) -> int:
    """Use a certain amount of memory in B"""
    bytearray(int(x))
    return x


def cpu_busy(execution_time: int) -> float:
    """Keeps the cpu busy for `execution_time` seconds

    Parameters
    ----------
    execution_time: int
        Amount of seconds to keep the cpu busy for
    """
    start = time.process_time()
    while True:
        duration = time.process_time() - start
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

    busy = 10

    with pytest.raises(CpuTimeoutException):
        with Pynisher(cpu_busy, memory=mem_limit, cpu_time=cputime_limit) as rf:
            print(rf(busy))


def test_memory_limit() -> None:
    """
    Expects
    -------
    * With a cputime limit set and a memory limit set, allocating too much memory
      should still raise a MemoryLimitException
    """
    mem_limit = (100, "MB")
    cputime_limit = 100

    allocate_mem = memconvert(200, frm="MB")

    with pytest.raises(MemoryLimitException):
        with Pynisher(usememory, memory=mem_limit, cpu_time=cputime_limit) as rf:
            rf(allocate_mem)
