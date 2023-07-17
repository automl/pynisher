from __future__ import annotations

import platform

from pynisher import CpuTimeoutException, Pynisher, contexts, supports_cputime

import pytest

from test.util import busy_wait

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
    with Pynisher(busy_wait, cpu_time=4, context=context) as rf:
        print(rf(1))


@pytest.mark.parametrize("context", contexts)
def test_fail(context: str) -> None:
    """
    Expects
    -------
    * The Pynisher process should raise a CpuTimeoutException when
      exceeding the time limit
    """
    with pytest.raises(CpuTimeoutException):
        with Pynisher(busy_wait, cpu_time=2, context=context) as rf:
            rf(20)
