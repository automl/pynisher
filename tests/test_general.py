import pytest
from typing import Optional

from pynisher import Pynisher
from pynisher.exceptions import TimeoutException
import time


def func() -> int:
    return


def func2(a: int, b: int) -> int:
    return a + b


def func3(a: int, b: Optional[int] = None, c: Optional[int] = None) -> int:
    if b is not None:
        a += b

    if c is not None:
        a += c

    return a


def test_interface():
    # Try a function without arguments
    with Pynisher(func) as restricted_func:
        result = restricted_func()
        assert result is None

    restricted_func = Pynisher(func)
    result = restricted_func()
    assert result is None

    # Try a function with args
    with Pynisher(func2) as restricted_func:
        result = restricted_func(5, 3)
        assert result == 8

    restricted_func = Pynisher(func2)
    result = restricted_func(5, 3)
    assert result == 8

    # Try a function with kwargs
    with Pynisher(func3) as restricted_func:
        result = restricted_func(5, c=3)
        assert result == 8

        result = restricted_func(5, b=3)
        assert result == 8

        result = restricted_func(5, b=3, c=2)
        assert result == 10

    restricted_func = Pynisher(func3)

    result = restricted_func(5, b=3)
    assert result == 8

    result = restricted_func(5, b=3, c=2)
    assert result == 10
