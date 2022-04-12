"""These tests ensure the API of how this can be used is enforced."""
from typing import Any

from pynisher import Pynisher, limit
import os

import pytest


def subfunction() -> int:
    return os.getpid()


def test_as_contextmanager() -> None:
    with Pynisher(subfunction) as restricted_func:
        other_process_id = restricted_func()

    this_process_id = os.getpid()
    assert this_process_id != other_process_id


def test_call() -> None:
    restricted_func = Pynisher(subfunction)

    this_process_id = os.getpid()
    other_process_id = restricted_func()

    assert this_process_id != other_process_id


def test_run() -> None:
    """Checks with explicit"""
    pynisher = Pynisher(subfunction)

    this_process_id = os.getpid()
    other_process_id = pynisher.run()
    assert this_process_id != other_process_id


def test_limit_gives_helpful_err_message_with_misuse() -> None:
    """NOTE: Not advised usage pattern"""

    with pytest.raises(ValueError, match=r"Please pass arguments to decorator `limit`"):

        @limit
        def f(x: int) -> int:
            return x


def test_limit_as_decorator() -> None:
    """NOTE: Not advised usage pattern"""

    @limit(name="hello")
    def f() -> int:
        return subfunction()

    this_process_id = os.getpid()
    other_process_id = f()
    assert this_process_id != other_process_id
