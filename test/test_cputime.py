from __future__ import annotations

import platform

from pynisher import CpuTimeoutException, Pynisher, contexts, supports_cputime

import pytest

from test.util import cputime_sleep

if not supports_cputime():
    pytest.skip(
        f"Can't limit cputime on {platform.platform()}",
        allow_module_level=True,
    )


@pytest.mark.parametrize("context", contexts)
def test_success(context: str) -> None:
    """
    Expects
    -------
    * Should raise no error and execute te function
    """
    with Pynisher(cputime_sleep, cpu_time=3, context=context) as rf:
        print(rf(2))


@pytest.mark.parametrize("cpu_time", [2, 3])
@pytest.mark.parametrize("context", contexts)
def test_fail(cpu_time: int, context: str) -> None:
    """
    Expects
    -------
    * The Pynisher process should raise a CpuTimeoutException when
      exceeding the time limit
    """
    with pytest.raises(CpuTimeoutException):

        with Pynisher(
            cputime_sleep,
            cpu_time=cpu_time,
            context=context,
        ) as rf:
            over_limit = cpu_time * 3
            print(rf(over_limit))
