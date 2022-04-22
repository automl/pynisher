import platform
import time

from pynisher import Pynisher, TimeoutException, supports_walltime

import pytest

if not supports_walltime():
    pytest.skip(
        f"Can't limit walltime on {platform.platform()}",
        allow_module_level=True,
    )


def func(sleep: float) -> bool:
    """Sleep for `sleep` seconds"""
    time.sleep(sleep)
    return True


@pytest.mark.parametrize("wall_time", [1, 2])
def test_fail(wall_time: int) -> None:
    """
    Expects
    -------
    * Should fail when the method uses more time than given
    """
    with pytest.raises(TimeoutException):
        with Pynisher(func, wall_time=wall_time) as restricted_func:
            restricted_func(sleep=wall_time * 2)


def test_success() -> None:
    """
    Expects
    -------
    * Should complete successfully if using less time than given
    """
    with Pynisher(func, wall_time=5) as restricted_func:
        restricted_func(sleep=1)
