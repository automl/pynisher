"""These tests ensure the API of how this can be used is enforced."""
import os
import sys

from pynisher import Pynisher, limit

import pytest

parametrize = pytest.mark.parametrize
plat = sys.platform


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


def test_bad_func_arg() -> None:
    """
    Expects
    -------
    * Should raise an Error about a none callable bad memory limit
    """
    with pytest.raises(ValueError, match=r"func"):
        Pynisher(func=None)  # type: ignore


@parametrize("memory", [-1, 0])
def test_bad_memory_arg(memory: int) -> None:
    """
    Expects
    -------
    * Should raise an Error about a bad memory limit
    """
    with pytest.raises(ValueError, match=r"memory"):
        Pynisher(subfunction, memory=memory)


@parametrize("cpu_time", [-1, 0])
def test_bad_cpu_time_arg(cpu_time: int) -> None:
    """
    Expects
    -------
    * Should raise an Error about a bad cpu_time limit
    """

    def _f() -> None:
        pass

    with pytest.raises(ValueError, match=r"cpu_time"):
        Pynisher(_f, cpu_time=cpu_time)


@parametrize("wall_time", [-1, 0])
def test_bad_wall_time_arg(wall_time: int) -> None:
    """
    Expects
    -------
    * Should raise an Error about a bad wall_time limit
    """

    def _f() -> None:
        pass

    with pytest.raises(ValueError, match=r"wall_time"):
        Pynisher(_f, wall_time=wall_time)


@parametrize("grace_period", [-1, 0])
def test_bad_grace_period_arg(grace_period: int) -> None:
    """
    Expects
    -------
    * Should raise an Error about a bad grace_period limit
    """

    def _f() -> None:
        pass

    with pytest.raises(ValueError, match=r"grace_period"):
        Pynisher(_f, grace_period=grace_period)


def test_bad_context_arg() -> None:
    """
    Expects
    -------
    * Should raise an Error about a bad grace_period limit
    """

    def _f() -> None:
        pass

    with pytest.raises(ValueError, match=r"context"):
        Pynisher(_f, context="bad arg")


@pytest.mark.skipif(
    not (
        (plat.lower().startswith("win") or plat.startswith("darwin"))
        and sys.version_info >= (3, 8)
    ),
    reason="@limit is only supported on Linux or Windows/Mac when Python < 3.8",
)
def test_limit_raises_if_not_supported() -> None:
    """
    Expects
    -------
    * Should raise an Error if limit is not supported
    """
    with pytest.raises(RuntimeError, match=r"Due to how multiprocessing*"):

        @limit(name="hello")
        def limited_func_with_decorator() -> int:
            pass
