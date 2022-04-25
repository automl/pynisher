import os
import platform

from pynisher import contexts, limit

import pytest


@limit(name="hello", context="fork")
def limited_func_with_decorator_fork() -> None:
    """A limit function"""
    pass


@limit(name="hello", context="forkserver")
def limited_func_with_decorator_forkserver() -> None:
    """A limit function"""
    pass


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


def test_limit_does_not_allow_spawn_context() -> None:
    """
    Expects
    -------
    * Should raise an error if decorator is used with 'spawn' context
    """
    with pytest.raises(ValueError):

        @limit(name="valid", context="spawn")
        def f(x: int) -> int:
            return x


@pytest.mark.skipif(
    "fork" not in contexts,
    reason=f"Platform {platform.platform()} does not supprt 'fork' context",
)
def test_limit_as_runs_as_seperate_process_fork() -> None:
    """
    Expects
    -------
    * Should be able to decorate function
    """
    this_process_id = os.getpid()
    other_process_id = limited_func_with_decorator_fork()
    assert this_process_id != other_process_id


@pytest.mark.skipif(
    "forkserver" not in contexts,
    reason=f"Platform {platform.platform()} does not supprt 'forkserver' context",
)
def test_limit_as_runs_as_seperate_process_forkserver() -> None:
    """
    Expects
    -------
    * Should be able to decorate function
    """
    this_process_id = os.getpid()
    other_process_id = limited_func_with_decorator_forkserver()
    assert this_process_id != other_process_id
