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
    while True:
        duration = time.perf_counter() - start
        if duration > execution_time:
            break

    return duration


def test_success() -> None:
    with Pynisher(func, cpu_time=3) as restricted_func:
        restricted_func(2)


def test_fail() -> None:
    """
    Expects
    -------
    * The Pynisher process should raise a CpuTimeoutException when
      exceeding the time limit
    """
    with pytest.raises(CpuTimeoutException):
        with Pynisher(func, cpu_time=1) as restricted_func:
            restricted_func(2)
