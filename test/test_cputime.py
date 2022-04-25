import platform
import time

from pynisher import CpuTimeoutException, Pynisher, contexts, supports_cputime

import pytest

if not supports_cputime():
    pytest.skip(
        f"Can't limit cputime on {platform.platform()}",
        allow_module_level=True,
    )


def func(execution_time: float) -> float:
    """
    Sleeps for `sleep` second.

    Warning
    -------
    print statements do not count towards the time limit.
    """
    start = time.perf_counter()
    while True:
        duration = time.perf_counter() - start
        if duration > execution_time:
            break

    return duration


@pytest.mark.parametrize("context", contexts)
def test_success(context: str) -> None:
    """
    Expects
    -------
    * Should raise no error and execute te function
    """
    with Pynisher(func, cpu_time=3, context=context) as restricted_func:
        restricted_func(2)


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
            over_limit = cpu_time + grace_period + 1
            rf(over_limit)
