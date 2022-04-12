from pynisher import Pynisher
from pynisher.exceptions import CpuTimeoutException
import time

import pytest


def func() -> None:
    time.sleep(3)


def test_fail() -> None:
    with pytest.raises(CpuTimeoutException):

        with Pynisher(func, cpu_time=1) as restricted_func:
            restricted_func()


def test_success() -> None:
    with Pynisher(func, cpu_time=5) as restricted_func:
        restricted_func()
