"""These tests ensure the API of how this can be used is enforced."""
import os
import time

from pynisher import EMPTY, Pynisher, contexts, supports
from pynisher.util import memconvert

import pytest


def subfunction() -> int:
    """Small test function which returns the id"""
    return os.getpid()


def err_function() -> None:
    """Function that raises an error"""
    raise RuntimeError("Error from test func `err_function`")


def sleepy(sleep: float) -> None:
    """Sleeps for `sleep` second"""
    start = time.perf_counter()
    while True:
        duration = time.perf_counter() - start
        if duration > sleep:
            break


def usememory(x: int) -> None:
    """Use a certain amount of memory in B"""
    bytearray(int(x))
    return x


def return_none() -> None:
    """Just returns None to make sure we pass it back correctly"""
    return None


@pytest.mark.parametrize("context", contexts)
def test_as_contextmanager(context: str) -> None:
    """
    Expects
    -------
    * Should be able to use as a context manager
    """
    with Pynisher(subfunction, context=context) as restricted_func:
        other_process_id = restricted_func()

    this_process_id = os.getpid()
    assert this_process_id != other_process_id


@pytest.mark.parametrize("context", contexts)
def test_call(context: str) -> None:
    """
    Expects
    -------
    * Should be able to call the restricted function
    """
    restricted_func = Pynisher(subfunction, context=context)

    this_process_id = os.getpid()
    other_process_id = restricted_func()

    assert this_process_id != other_process_id


@pytest.mark.parametrize("context", contexts)
def test_run(context: str) -> None:
    """
    Expects
    -------
    * Should be able to explicitly call run on the restricted function
    """
    pynisher = Pynisher(subfunction, context=context)

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


@pytest.mark.parametrize("memory", [-1, 0])
def test_bad_memory_arg(memory: int) -> None:
    """
    Expects
    -------
    * Should raise an Error about a bad memory limit
    """
    with pytest.raises(ValueError, match=r"memory"):
        Pynisher(subfunction, memory=memory)


@pytest.mark.parametrize("cpu_time", [-1, 0])
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


@pytest.mark.parametrize("wall_time", [-1, 0])
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


@pytest.mark.parametrize("grace_period", [-1, 0])
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


def test_no_raise_gets_empty() -> None:
    """
    Expects
    -------
    * Setting `raises=False` on a function that raises should return EMPTY
    """
    rf = Pynisher(err_function, raises=False)
    result = rf()
    assert result is EMPTY


@pytest.mark.skipif(not supports("walltime"), reason="System doesn't support walltime")
def test_walltime_no_raise_gets_empty() -> None:
    """
    Expects
    -------
    * No raise should return empty if there was a wall time limit reached
    """
    rf = Pynisher(err_function, wall_time=1, raises=False)
    result = rf()
    assert result is EMPTY


@pytest.mark.skipif(not supports("walltime"), reason="System doesn't support cputime")
def test_cputime_no_raise_gets_empty() -> None:
    """
    Expects
    -------
    * No raise should return empty if there was a cputime out
    """
    rf = Pynisher(sleepy, cpu_time=1, raises=False)
    result = rf(10000)
    assert result is EMPTY


@pytest.mark.skipif(not supports("memory"), reason="System doesn't support memory")
def test_memory_no_raise_gets_empty() -> None:
    """
    Expects
    -------
    * No raise should return empty if there was a memort limit reached
    """
    rf = Pynisher(usememory, memory=(1, "B"), raises=False)
    result = rf(memconvert(1, frm="mb"))
    assert result is EMPTY


def test_func_can_return_none() -> None:
    """
    Expects
    -------
    * A function return None should recieve None as the answer, making sure
      we don't accidentally eat it while processing everything.
    """
    rf = Pynisher(return_none)
    result = rf()
    assert result is None
