import os
import platform

from pynisher import restricted, supports_limit_decorator

import pytest

if not supports_limit_decorator():
    pytest.skip(
        f"Can't use @restricted on {platform.platform()}",
        allow_module_level=True,
    )


@restricted(name="hello", context="fork")
def limited_func_with_decorator_fork() -> None:
    """A limit function"""
    pass


@restricted(name="hello", context="forkserver")
def limited_func_with_decorator_forkserver() -> None:
    """A limit function"""
    pass


def test_limit_gives_helpful_err_message_with_misuse() -> None:
    """
    Expects
    -------
    * Should raise an error if decorator is used without arguments
    """
    msg = r"Please pass arguments to decorator `@restricted`"
    with pytest.raises(ValueError, match=msg):

        @restricted  # type: ignore
        def f(x: int) -> int:
            return x


def test_limit_as_runs_with_spawn_raises() -> None:
    """
    Expects
    -------
    * Should be able to run in spawn context
    """
    with pytest.raises(ValueError):

        @restricted(name="hello", context="spawn")
        def limited_func_with_decorator_spawn() -> None:
            """A restricted function"""
            pass


def test_limit_as_runs_as_seperate_process_fork() -> None:
    """
    Expects
    -------
    * Should be able to run in fork context
    """
    this_process_id = os.getpid()
    other_process_id = limited_func_with_decorator_fork()
    assert this_process_id != other_process_id


def test_limit_as_runs_as_seperate_process_forkserver() -> None:
    """
    Expects
    -------
    * Should be able to run in forkserver context
    """
    this_process_id = os.getpid()
    other_process_id = limited_func_with_decorator_forkserver()
    assert this_process_id != other_process_id
