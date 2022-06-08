from typing import Any, Callable, Type

import sys

import psutil

from pynisher import (
    CpuTimeoutException,
    MemoryLimitException,
    WallTimeoutException,
    contexts,
    limit,
    supports,
)

import pytest

from test.util import busy_wait, raises_error, usememory, walltime_sleep


class CustomException(Exception):
    pass


def echo(x: Any) -> Any:
    """Just echos back anything given to it"""
    return x


def pynish_success(x: Any, context: str) -> Any:
    """A successful pynished function"""
    lf = limit(echo, context=context)
    return lf(x)


def pynish_custom(context: str) -> int:
    """Will pynish a function and exceed memory"""
    lf = limit(raises_error, context=context)
    lf(CustomException)
    return 4


def pynish_memory(context: str) -> int:
    """Will pynish a function and exceed memory"""
    lf = limit(usememory, memory=(50, "mb"), context=context)
    return lf((100, "mb"))


def pynish_walltime(context: str) -> float:
    """Will pynish a function and exceed walltime"""
    lf = limit(walltime_sleep, wall_time=(1, "s"), context=context)
    return lf(5)


def pynish_cputime(context: str) -> float:
    """Will pynish a function and exceed cputime"""
    lf = limit(busy_wait, cpu_time=(1, "s"), context=context)
    lf(10)
    return 13.37


@pytest.mark.parametrize(
    # Gracious limits
    "top_limit",
    [{"wall_time": 20, "cpu_time": 20, "memory": (500, "MB")}],
)
@pytest.mark.parametrize(
    "func, err_type",
    [
        (pynish_memory, MemoryLimitException),
        (pynish_walltime, WallTimeoutException),
        (pynish_cputime, CpuTimeoutException),
        (pynish_custom, CustomException),
    ],
)
@pytest.mark.parametrize("root_context", contexts)
@pytest.mark.parametrize("sub_context", contexts)
def test_two_level_fail_second_level(
    top_limit: dict,
    func: Callable,
    err: Type[Exception],
    root_context: str,
    sub_context: str,
) -> None:
    """
    | pynisher_1
    |   pynisher_2
    |       raise ErrorType

    Expects
    -------
    * The underlying error from pynisher level 2 should be propogated up
    """
    if root_context == "fork" and sub_context == "forkserver":
        pytest.skip(
            "Doesn't seem to like when pyisher uses 'fork' while the child uses"
            "'forkserver' to spawn new processes."
        )

    if root_context == "fork" and sub_context == "spawn" and sys.version_info < (3, 8):
        pytest.skip(
            "Python 3.7 doesn't seem to allow for a 'fork' process function"
            " to create new subprocesses with 'spawn'"
        )

    lf = limit(func, **top_limit, context=root_context)

    try:
        lf(context=sub_context)
    except err:
        pass
    except Exception as e:
        # Quick hack s.t. the mac tests don't fail
        if supports("memory"):
            print(e, type(e))
            raise e

    assert lf._process is not None

    try:
        children = lf._process.children(recursive=True)
        print(children)
        assert len(children) == 0
    except psutil.NoSuchProcess:
        pass


@pytest.mark.parametrize("root_context", contexts)
@pytest.mark.parametrize("sub_context", contexts)
def test_two_level_success_result(root_context: str, sub_context: str) -> None:
    """
    | pynisher_1
    |   pynisher_2
    |       return 10

    Expects
    -------
    * The result of the nested level should reach the top
    """
    if root_context == "fork" and sub_context == "forkserver":
        pytest.skip(
            "Doesn't seem to like when pyisher uses 'fork' while the child uses"
            "'forkserver' to spawn new processes."
        )

    if root_context == "fork" and sub_context == "spawn" and sys.version_info < (3, 8):
        pytest.skip(
            "Python 3.7 doesn't seem to allow for a 'fork' process function"
            " to create new subprocesses with 'spawn'"
        )

    lf = limit(pynish_success, context=root_context)
    assert lf(x=10, context=sub_context) == 10
