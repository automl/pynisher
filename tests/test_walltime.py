from pynisher import Pynisher
from pynisher.exceptions import TimeoutException
import time

import pytest

def func(sleep: float) -> bool:
    """Sleep for `sleep` seconds"""
    time.sleep(sleep)
    return True


def test_fail() -> None:
    """
    Expects
    -------
    * Should fail when the method uses more time than given
    """
    with pytest.raises(TimeoutException):
        with Pynisher(func, wall_time=1) as restricted_func:
            completed = False
            completed = restricted_func(sleep=2)

    assert not completed


def test_success() -> None:
    """
    Expects
    -------
    * Should complete successfully if using less time than given
    """
    with Pynisher(func, wall_time=5) as restricted_func:
        restricted_func(sleep=1)
