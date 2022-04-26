from __future__ import annotations

import platform
import time

from pynisher import CpuTimeoutException, Pynisher, contexts, supports_cputime

import pytest

if not supports_cputime():
    pytest.skip(
        f"Can't limit cputime on {platform.platform()}",
        allow_module_level=True,
    )


def func(execution_time: float) -> tuple[float, int]:
    """
    Sleeps for `sleep` second.

    Warning
    -------
    print statements do not count towards the time limit.
    """
    x = 0
    start = time.process_time()
    while True:
        x += 1
        duration = time.process_time() - start
        if duration > execution_time:
            break

    return (duration, x)


@pytest.mark.parametrize("context", contexts)
def test_success(context: str) -> None:
    """
    Expects
    -------
    * Should raise no error and execute te function
    """
    with Pynisher(func, cpu_time=3, context=context) as restricted_func:
        print(restricted_func(2))


@pytest.mark.parametrize("cpu_time", [1, 2])
@pytest.mark.parametrize("grace_period", [1, 2])
@pytest.mark.parametrize("context", contexts)
def test_fail(cpu_time: int, grace_period: int, context: str) -> None:
    """
    Expects
    -------
    * The Pynisher process should raise a CpuTimeoutException when
      exceeding the time limit
    """
    with pytest.raises(CpuTimeoutException):

        with Pynisher(
            func,
            cpu_time=cpu_time,
            grace_period=grace_period,
            context=context,
        ) as rf:
            over_limit = (cpu_time + grace_period) * 3
            print(rf(over_limit))
