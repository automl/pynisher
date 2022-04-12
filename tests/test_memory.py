import time
import sys
from pynisher import Pynisher
from pynisher.exceptions import MemorylimitException


def func() -> int:
    array = [i for i in range(10000000)]
    # This array is approx 84.97 MB
    # size = sys.getsizeof(array) / 1024 / 1024
    return


def test_fail():
    try:
        with Pynisher(func, memory=90) as restricted_func:
            restricted_func()
    except MemorylimitException:
        pass


def test_success():
    with Pynisher(func, memory=5) as restricted_func:
        restricted_func()
