from pynisher import Pynisher
from pynisher.exceptions import CpuTimeoutException
import time

import pytest


def func(execution_time: float) -> float:
    """
    Sleeps for `sleep` second.

    Warning
    -------
    print statements do not count towards the time limit.
    """
    start = time.perf_counter()
    x = 1
    while True:
        duration = time.perf_counter() - start
        x += 1
        if duration > execution_time:
            break

    return duration, x


def test_success() -> None:
    with Pynisher(func, cpu_time=3) as restricted_func:
        restricted_func(2)


@pytest.mark.parametrize("cpu_time", [0, 0.1, 0.5, 1, 1.5, 2])
@pytest.mark.parametrize("grace_period", [0, 0.1, 0.5, 1])
def test_fail(cpu_time: float, grace_period: float) -> None:
    """
    Expects
    -------
    * The Pynisher process should raise a CpuTimeoutException when
      exceeding the time limit
    """
    with pytest.raises(CpuTimeoutException):
        with Pynisher(func, cpu_time=cpu_time, grace_period=grace_period) as rf:
            over_limit = cpu_time + grace_period + 1
            rf(over_limit)
