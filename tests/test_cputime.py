from pynisher import Pynisher
from pynisher.exceptions import CpuTimeoutException
import time

import pytest


def func(sleep: float) -> bool:
    """Sleeps for `sleep` second"""
    time.sleep(sleep)
    return True


def test_fail() -> None:
    """
    Expects
    -------
    * The Pynisher process should raise a CpuTimeoutException when
      exceeding the time limit
    """
    with pytest.raises(CpuTimeoutException):
        with Pynisher(func, cpu_time=1) as restricted_func:
            completed = False
            completed = restricted_func(sleep=3)

    assert not completed


def test_success() -> None:
    """
    Expects
    -------
    * The Pynisher process should complete successfully without an issue
    """
    with Pynisher(func, cpu_time=5) as restricted_func:
        completed = restricted_func(sleep=1)

    assert completed is True
