from __future__ import annotations

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


@pytest.mark.parametrize("memory_limit", [(500, "MB"), None])
@pytest.mark.parametrize("wall_time_limit", [(20, "s"), None])
@pytest.mark.parametrize("cpu_time_limit", [(20, "s"), None])
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
    memory_limit: tuple | None,
    wall_time_limit: tuple | None,
    cpu_time_limit: tuple | None,
    func: Callable,
    err_type: Type[Exception],
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
    * All of the processes children should be terminated
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

    if (memory_limit is not None or err_type is MemoryLimitException) and not supports(
        "memory"
    ):
        pytest.skip(f"System {sys.platform} does not support 'memory' limiting")

    if (cpu_time_limit is not None or err_type is CpuTimeoutException) and not supports(
        "cpu_time"
    ):
        pytest.skip(f"System {sys.platform} does not support 'cpu_time' limiting")

    if (
        wall_time_limit is not None or err_type is WallTimeoutException
    ) and not supports("wall_time"):
        pytest.skip(f"System {sys.platform} does not support 'wall_time' limiting")

    # The function being limitied will raise one of the specific errors
    # as seen in `parametrize` above
    top_limit = {
        "memory": memory_limit,
        "wall_time": wall_time_limit,
        "cpu_time": cpu_time_limit,
    }
    lf = limit(func, **top_limit, context=root_context)

    try:
        lf(context=sub_context)
    except BaseException as e:
        # We should catch the expected error type as it propgates up, in which
        # case everything is working as intended and we move on
        assert isinstance(e, err_type)

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
