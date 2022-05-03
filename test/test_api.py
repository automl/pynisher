"""These tests ensure the API of how this can be used is enforced."""
import os

from pynisher import EMPTY, Pynisher, contexts, limit, supports

import pytest

from test.util import busy_wait, get_process_id, raises_error, return_none, usememory


@pytest.mark.parametrize("context", contexts)
def test_as_contextmanager(context: str) -> None:
    """
    Expects
    -------
    * Should be able to use as a context manager
    """
    with Pynisher(get_process_id, context=context) as rf:
        other_process_id = rf()

    this_process_id = os.getpid()
    assert this_process_id != other_process_id


@pytest.mark.parametrize("context", contexts)
def test_call(context: str) -> None:
    """
    Expects
    -------
    * Should be able to call the restricted function
    """
    rf = Pynisher(get_process_id, context=context)

    this_process_id = os.getpid()
    other_process_id = rf()

    assert this_process_id != other_process_id


@pytest.mark.parametrize("context", contexts)
def test_limit_usage(context: str) -> None:
    """
    Expects
    -------
    * Should be able to use in the `limit` api usage
    """
    with limit(get_process_id, context=context) as rf:
        this_process_id = os.getpid()
        other_process_id = rf()

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
        Pynisher(get_process_id, memory=memory)


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


def test_bad_context_arg() -> None:
    """
    Expects
    -------
    * Should raise an Error about a bad context arg
    """

    def _f() -> None:
        pass

    with pytest.raises(ValueError, match=r"context"):
        Pynisher(_f, context="bad arg")


@pytest.mark.parametrize("context", contexts)
def test_no_raise_gets_empty(context: str) -> None:
    """
    Expects
    -------
    * Setting `raises=False` on a function that raises should return EMPTY
    """
    rf = Pynisher(raises_error, raises=False, context=context)
    result = rf()
    assert result is EMPTY


@pytest.mark.skipif(
    not supports("wall_time"), reason="System doesn't support wall_time"
)
@pytest.mark.parametrize("context", contexts)
def test_walltime_no_raise_gets_empty(context: str) -> None:
    """
    Expects
    -------
    * No raise should return empty if there was a wall time limit reached
    """
    rf = Pynisher(raises_error, wall_time=1, raises=False, context=context)
    result = rf()
    assert result is EMPTY


@pytest.mark.skipif(not supports("wall_time"), reason="System doesn't support cpu_time")
@pytest.mark.parametrize("context", contexts)
def test_cputime_no_raise_gets_empty(context: str) -> None:
    """
    Expects
    -------
    * No raise should return empty if there was a cputime out
    """
    rf = Pynisher(busy_wait, cpu_time=1, raises=False, context=context)
    result = rf(10000)
    assert result is EMPTY


@pytest.mark.skipif(not supports("memory"), reason="System doesn't support memory")
@pytest.mark.parametrize("context", contexts)
def test_memory_no_raise_gets_empty(context: str) -> None:
    """
    Expects
    -------
    * No raise should return empty if there was a memort limit reached
    """
    rf = Pynisher(usememory, memory=(1, "B"), raises=False, context=context)
    result = rf((1, "mb"))
    assert result is EMPTY


@pytest.mark.parametrize("context", contexts)
def test_func_can_return_none(context: str) -> None:
    """
    Expects
    -------
    * A function return None should recieve None as the answer, making sure
      we don't accidentally eat it while processing everything.
    """
    rf = Pynisher(return_none, context=context)
    result = rf()
    assert result is None
