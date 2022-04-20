"""These tests ensure the API of how this can be used is enforced."""
import os

from pynisher import Pynisher, limit

import pytest


def subfunction() -> int:
    """Small test function which returns the id"""
    return os.getpid()


def test_as_contextmanager() -> None:
    """
    Expects
    -------
    * Should be able to use as a context manager
    """
    with Pynisher(subfunction) as restricted_func:
        other_process_id = restricted_func()

    this_process_id = os.getpid()
    assert this_process_id != other_process_id


def test_call() -> None:
    """
    Expects
    -------
    * Should be able to call the restricted function
    """
    restricted_func = Pynisher(subfunction)

    this_process_id = os.getpid()
    other_process_id = restricted_func()

    assert this_process_id != other_process_id


def test_run() -> None:
    """
    Expects
    -------
    * Should be able to explicitly call run on the restricted function
    """
    pynisher = Pynisher(subfunction)

    this_process_id = os.getpid()
    other_process_id = pynisher.run()
    assert this_process_id != other_process_id


def test_limit_gives_helpful_err_message_with_misuse() -> None:
    """
    Expects
    -------
    * Should raise an error if decorator is used without arguments
    """
    with pytest.raises(ValueError, match=r"Please pass arguments to decorator `limit`"):

        @limit  # type: ignore
        def f(x: int) -> int:
            return x


def test_limit_as_decorator() -> None:
    """
    Expects
    -------
    * Should be able to decorate function
    """
    @limit(name="hello")
    def f() -> int:
        return subfunction()

    this_process_id = os.getpid()
    other_process_id = f()
    assert this_process_id != other_process_id
