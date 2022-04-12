from pynisher import Pynisher
from pynisher.exceptions import TimeoutException
import time


def func() -> int:
    time.sleep(3)


def test_fail():
    try:
        with Pynisher(func, wall_time=1) as restricted_func:
            restricted_func()
    except TimeoutException:
        pass


def test_success():
    with Pynisher(func, wall_time=5) as restricted_func:
        restricted_func()
